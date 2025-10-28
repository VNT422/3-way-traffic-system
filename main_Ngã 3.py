import random
import time
import threading
import pygame
import sys
import os
import numpy as np

# set prediction model for green time signal on / off
prediction_model_mode = True # Giữ nguyên là True để chế độ dự đoán hoạt động

import joblib

# Tạo một mô hình giả lập nếu bạn không có file "model_joblib"
class MockModel:
    def predict(self, flow_percentile):
        # Mô hình giả lập giờ đây trả về một HỆ SỐ ĐIỀU CHỈNH
        # Chuyển đổi flow_percentile thành một con số đơn
        if isinstance(flow_percentile, np.ndarray) and flow_percentile.size > 0:
            current_flow = flow_percentile.item() if flow_percentile.ndim == 0 else flow_percentile[0][0]
        else:
            current_flow = 0 # Hoặc một giá trị mặc định hợp lý
        
        # Một cách tính hệ số:
        adjustment_factor = 1.0 + (current_flow - 50) / 250.0 # Điều chỉnh hệ số theo lưu lượng
        adjustment_factor = max(0.7, min(1.3, adjustment_factor)) # Giới hạn hệ số từ 0.7 đến 1.3
        
        return np.array([adjustment_factor]) # Trả về mảng numpy như mô hình thực
        
# Thay đổi dòng này để tải mô hình thực hoặc sử dụng mô hình giả lập
try:
    mj = joblib.load("model_joblib")
except FileNotFoundError:
    print("model_joblib not found. Using a mock ML model for green time adjustment factor prediction.")
    mj = MockModel()


# Hàm này giờ đây trả về hệ số điều chỉnh, KHÔNG phải thời gian đèn xanh
def ml_model_adjustment_factor(flow):
    flow_percentile = np.array(flow).reshape(-1, 1)
    adjustment_factor = mj.predict(flow_percentile)
    
    # Giới hạn hệ số để tránh thời gian đèn xanh quá ngắn hoặc quá dài một cách bất hợp lý
    adjustment_factor = max(0.7, min(1.3, adjustment_factor.item())) # Giới hạn từ 0.7 đến 1.3
    return adjustment_factor


# Default values of signal timers
a0 = 12 - 2 # right
a2 = 12 - 2 # left
a3 = 12 - 2 # up
a4 = 15 - 2
# CHỈNH SỬA: Bỏ defaultGreen cho hướng down (1)
defaultGreen = {0: a0, 2: a2, 3: a3}
defaultRed = a4
defaultYellow = 3

signals = {} # CHỈNH SỬA: Chuyển sang dictionary để dễ quản lý các tín hiệu không liên tiếp
noOfSignals = 3 # CHỈNH SỬA: Chỉ còn 3 tín hiệu
currentGroup = 0  # Dùng để chỉ pha đèn đang xanh

currentYellow = 0  # 0 -> green phase, 1 -> yellow phase
signal_lock = threading.Lock()

speeds = {"car": 2.25, "bus": 1.8, "truck": 1.8, "bike": 2.5}

# CHỈNH SỬA: Bỏ tọa độ cho hướng 'down'
x = {
    "right": [0, 0, 0],
    "left": [1400, 1400, 1400],
    "up": [680, 723, 819],
}
y = {
    "right": [380, 410, 465],
    "left": [258, 315, 365],
    "up": [800, 800, 800],
}

# CHỈNH SỬA: Bỏ dictionary cho xe hướng 'down'
vehicles = {
    "right": {0: [], 1: [], 2: [], "crossed": 0},
    "left": {0: [], 1: [], 2: [], "crossed": 0},
    "up": {0: [], 1: [], 2: [], "crossed": 0},
}
vehicleTypes = {0: "car", 1: "bus", 2: "truck", 3: "bike"}
# CHỈNH SỬA: Bỏ hướng 'down'
directionNumbers = {0: "right", 2: "left", 3: "up"}
# CHỈNH SỬA: Danh sách các hướng đang hoạt động để dễ lặp lại
active_directions = [0, 2, 3]

# CHỈNH SỬA: Tọa độ cho 3 đèn (right, left, up)
signalCoods = [(300, 600), (1070, 100), (1070, 610)]
signalTimerCoods = [(300, 600), (1070, 100), (1070, 610)]
# CHỈNH SỬA: Ánh xạ từ ID hướng (0,2,3) sang chỉ số của list tọa độ (0,1,2)
display_idx_map = {0: 0, 2: 1, 3: 2}

# CHỈNH SỬA: Bỏ vạch dừng cho hướng 'down'
stopLines = {"right": 350, "left": 1050, "up": 603}
defaultStop = {"right": 340, "left": 1060, "up": 610}

stoppingGap = 25
movingGap = 30

allowedVehicleTypes = {"car": True, "bus": True, "truck": True, "bike": True}
allowedVehicleTypesList = []

# CHỈNH SỬA: Bỏ hướng 'down'
vehiclesTurned = {
    "right": {1: [], 2: []},
    "left": {1: [], 2: []},
    "up": {1: [], 2: []},
}
vehiclesNotTurned = {
    "right": {1: [], 2: []},
    "left": {1: [], 2: []},
    "up": {1: [], 2: []},
}

rotationAngle = 3

# CHỈNH SỬA: Bỏ hướng 'down'
mid = {
    "right": {"x": 560, "y": 465},
    "left": {"x": 860, "y": 310},
    "up": {"x": 815, "y": 495},
}

timeElapsed = 0
simulationTime = 0
timeElapsedCoods = (1050, 30)

# CHỈNH SỬA: Chỉ cần 3 bộ đếm xe
vehicleCountTexts = ["0", "0", "0"]
vehicleCountCoods = [(1050, 70), (1050, 110), (1050, 150)]

count_Leg1 = 0 # right
# count_Leg2 = 0 # CHỈNH SỬA: Bỏ leg 2 (down)
count_Leg3 = 0 # left
count_Leg4 = 0 # up

total_flow_count = 1
totalflowcoods = (10, 110)

pygame.init()
simulation = pygame.sprite.Group()


class TrafficSignal:
    def __init__(self, red, yellow, green):
        self.red = red
        self.yellow = yellow
        self.green = green
        self.signalText = ""


class Vehicle(pygame.sprite.Sprite):
    def __init__(self, lane, vehicleClass, direction_number, direction, will_turn):
        pygame.sprite.Sprite.__init__(self)
        self.lane = lane
        self.speed = speeds[vehicleClass]
        self.direction_number = direction_number
        self.direction = direction
        self.x = x[direction][lane]
        self.y = y[direction][lane]
        self.crossed = 0
        self.willTurn = will_turn
        self.turned = 0
        self.rotateAngle = 0
        vehicles[direction][lane].append(self)
        self.index = len(vehicles[direction][lane]) - 1
        self.crossedIndex = 0
        path = "./images/" + direction + "/" + vehicleClass + ".png"
        self.originalImage = pygame.image.load(path)
        self.image = pygame.image.load(path)

        if (
            len(vehicles[direction][lane]) > 1
            and vehicles[direction][lane][self.index - 1].crossed == 0
        ):
            if direction == "right":
                self.stop = (
                    vehicles[direction][lane][self.index - 1].stop
                    - vehicles[direction][lane][self.index - 1].image.get_rect().width
                    - stoppingGap
                )
            elif direction == "left":
                self.stop = (
                    vehicles[direction][lane][self.index - 1].stop
                    + vehicles[direction][lane][self.index - 1].image.get_rect().width
                    + stoppingGap
                )
            # CHỈNH SỬA: Xóa elif cho 'down'
            elif direction == "up":
                self.stop = (
                    vehicles[direction][lane][self.index - 1].stop
                    + vehicles[direction][lane][self.index - 1].image.get_rect().height
                    + stoppingGap
                )
        else:
            self.stop = defaultStop[direction]

        if direction == "right":
            temp = self.image.get_rect().width + stoppingGap
            x[direction][lane] -= temp
        elif direction == "left":
            temp = self.image.get_rect().width + stoppingGap
            x[direction][lane] += temp
        # CHỈNH SỬA: Xóa elif cho 'down'
        elif direction == "up":
            temp = self.image.get_rect().height + stoppingGap
            y[direction][lane] += temp
        simulation.add(self)

    def render(self, screen):
        screen.blit(self.image, (self.x, self.y))

    def move(self):
        # group 0 (0 & 2) -> directions right & left
        # group 1 (3)     -> direction up

        if self.direction == "right":
            if (self.crossed == 0 and self.x + self.image.get_rect().width > stopLines[self.direction]):
                self.crossed = 1
                vehicles[self.direction]["crossed"] += 1
                if self.willTurn == 0:
                    vehiclesNotTurned[self.direction][self.lane].append(self)
                    self.crossedIndex = len(vehiclesNotTurned[self.direction][self.lane]) - 1
            if self.willTurn == 1:
                if self.lane == 1:
                    if (self.crossed == 0 or self.x + self.image.get_rect().width < stopLines[self.direction] + 365):
                        if (self.x + self.image.get_rect().width <= self.stop or (currentGroup == 0 and currentYellow == 0) or self.crossed == 1) and (self.index == 0 or self.x + self.image.get_rect().width < (vehicles[self.direction][self.lane][self.index - 1].x - movingGap) or vehicles[self.direction][self.lane][self.index - 1].turned == 1):
                            self.x += self.speed
                    else:
                        if self.turned == 0:
                            self.rotateAngle += rotationAngle
                            self.image = pygame.transform.rotate(self.originalImage, self.rotateAngle)
                            self.x += 2.4
                            self.y -= 2.8
                            if self.rotateAngle == 90:
                                self.turned = 1
                                vehiclesTurned[self.direction][self.lane].append(self)
                                self.crossedIndex = len(vehiclesTurned[self.direction][self.lane]) - 1
                        else:
                            if self.crossedIndex == 0 or (self.y > (vehiclesTurned[self.direction][self.lane][self.crossedIndex - 1].y + vehiclesTurned[self.direction][self.lane][self.crossedIndex - 1].image.get_rect().height + movingGap)):
                                self.y -= self.speed
                elif self.lane == 2:
                    if (self.crossed == 0 or self.x + self.image.get_rect().width < mid[self.direction]["x"]):
                        if (self.x + self.image.get_rect().width <= self.stop or (currentGroup == 0 and currentYellow == 0) or self.crossed == 1) and (self.index == 0 or self.x + self.image.get_rect().width < (vehicles[self.direction][self.lane][self.index - 1].x - movingGap) or vehicles[self.direction][self.lane][self.index - 1].turned == 1):
                            self.x += self.speed
                    else:
                        if self.turned == 0:
                            self.rotateAngle += rotationAngle
                            self.image = pygame.transform.rotate(self.originalImage, -self.rotateAngle)
                            self.x += 2
                            self.y += 1.8
                            if self.rotateAngle == 90:
                                self.turned = 1
                                vehiclesTurned[self.direction][self.lane].append(self)
                                self.crossedIndex = len(vehiclesTurned[self.direction][self.lane]) - 1
                        else:
                            if self.crossedIndex == 0 or ((self.y + self.image.get_rect().height) < (vehiclesTurned[self.direction][self.lane][self.crossedIndex - 1].y - movingGap)):
                                self.y += self.speed
            else:
                if self.crossed == 0:
                    if (self.x + self.image.get_rect().width <= self.stop or (currentGroup == 0 and currentYellow == 0)) and (self.index == 0 or self.x + self.image.get_rect().width < (vehicles[self.direction][self.lane][self.index - 1].x - movingGap)):
                        self.x += self.speed
                else:
                    if (self.crossedIndex == 0) or (self.x + self.image.get_rect().width < (vehiclesNotTurned[self.direction][self.lane][self.crossedIndex - 1].x - movingGap)):
                        self.x += self.speed

        elif self.direction == "left":
            if self.crossed == 0 and self.x < stopLines[self.direction]:
                self.crossed = 1
                vehicles[self.direction]["crossed"] += 1
                if self.willTurn == 0:
                    vehiclesNotTurned[self.direction][self.lane].append(self)
                    self.crossedIndex = len(vehiclesNotTurned[self.direction][self.lane]) - 1
            if self.willTurn == 1:
                if self.lane == 2:
                    if self.crossed == 0 or self.x > stopLines[self.direction] - 440:
                        if (self.x >= self.stop or (currentGroup == 0 and currentYellow == 0) or self.crossed == 1) and (self.index == 0 or self.x > (vehicles[self.direction][self.lane][self.index - 1].x + vehicles[self.direction][self.lane][self.index - 1].image.get_rect().width + movingGap) or vehicles[self.direction][self.lane][self.index - 1].turned == 1):
                            self.x -= self.speed
                    else:
                        if self.turned == 0:
                            self.rotateAngle += rotationAngle
                            self.image = pygame.transform.rotate(self.originalImage, self.rotateAngle)
                            self.x -= 1
                            self.y += 1.2
                            if self.rotateAngle == 90:
                                self.turned = 1
                                vehiclesTurned[self.direction][self.lane].append(self)
                                self.crossedIndex = len(vehiclesTurned[self.direction][self.lane]) - 1
                        else:
                            if self.crossedIndex == 0 or ((self.y + self.image.get_rect().height) < (vehiclesTurned[self.direction][self.lane][self.crossedIndex - 1].y - movingGap)):
                                self.y += self.speed
                elif self.lane == 1:
                    if self.crossed == 0 or self.x > mid[self.direction]["x"]:
                        if (self.x >= self.stop or (currentGroup == 0 and currentYellow == 0) or self.crossed == 1) and (self.index == 0 or self.x > (vehicles[self.direction][self.lane][self.index - 1].x + vehicles[self.direction][self.lane][self.index - 1].image.get_rect().width + movingGap) or vehicles[self.direction][self.lane][self.index - 1].turned == 1):
                            self.x -= self.speed
                    else:
                        if self.turned == 0:
                            self.rotateAngle += rotationAngle
                            self.image = pygame.transform.rotate(self.originalImage, -self.rotateAngle)
                            self.x -= 1.8
                            self.y -= 2.5
                            if self.rotateAngle == 90:
                                self.turned = 1
                                vehiclesTurned[self.direction][self.lane].append(self)
                                self.crossedIndex = len(vehiclesTurned[self.direction][self.lane]) - 1
                        else:
                            if self.crossedIndex == 0 or (self.y > (vehiclesTurned[self.direction][self.lane][self.crossedIndex - 1].y + vehiclesTurned[self.direction][self.lane][self.crossedIndex - 1].image.get_rect().height + movingGap)):
                                self.y -= self.speed
            else:
                if self.crossed == 0:
                    if (self.x >= self.stop or (currentGroup == 0 and currentYellow == 0)) and (self.index == 0 or self.x > (vehicles[self.direction][self.lane][self.index - 1].x + vehicles[self.direction][self.lane][self.index - 1].image.get_rect().width + movingGap)):
                        self.x -= self.speed
                else:
                    if (self.crossedIndex == 0) or (self.x > (vehiclesNotTurned[self.direction][self.lane][self.crossedIndex - 1].x + vehiclesNotTurned[self.direction][self.lane][self.crossedIndex - 1].image.get_rect().width + movingGap)):
                        self.x -= self.speed

        elif self.direction == "up":
            if self.crossed == 0 and self.y < stopLines[self.direction]:
                self.crossed = 1
                vehicles[self.direction]["crossed"] += 1
                # Xe từ 'up' luôn rẽ nên không cần thêm vào 'vehiclesNotTurned'
            
            # THAY ĐỔI: Toàn bộ logic bên dưới là dành cho xe rẽ.
            # Khối `else` (cho xe đi thẳng) đã bị xóa.
            if self.lane == 1: # Rẽ trái
                if self.crossed == 0 or self.y > stopLines[self.direction] - 200:
                    if (self.y >= self.stop or (currentGroup == 1 and currentYellow == 0) or self.crossed == 1) and (self.index == 0 or self.y > (vehicles[self.direction][self.lane][self.index - 1].y + vehicles[self.direction][self.lane][self.index - 1].image.get_rect().height + movingGap) or vehicles[self.direction][self.lane][self.index - 1].turned == 1):
                        self.y -= self.speed
                else:
                    if self.turned == 0:
                        self.rotateAngle += rotationAngle
                        self.image = pygame.transform.rotate(self.originalImage, self.rotateAngle)
                        self.x -= 2
                        self.y -= 1.2
                        if self.rotateAngle == 90:
                            self.turned = 1
                            vehiclesTurned[self.direction][self.lane].append(self)
                            self.crossedIndex = len(vehiclesTurned[self.direction][self.lane]) - 1
                    else:
                        if self.crossedIndex == 0 or (self.x > (vehiclesTurned[self.direction][self.lane][self.crossedIndex - 1].x + vehiclesTurned[self.direction][self.lane][self.crossedIndex - 1].image.get_rect().width + movingGap)):
                            self.x -= self.speed
            elif self.lane == 2: # Rẽ phải
                if self.crossed == 0 or self.y > mid[self.direction]["y"]:
                    if (self.y >= self.stop or (currentGroup == 1 and currentYellow == 0) or self.crossed == 1) and (self.index == 0 or self.y > (vehicles[self.direction][self.lane][self.index - 1].y + vehicles[self.direction][self.lane][self.index - 1].image.get_rect().height + movingGap) or vehicles[self.direction][self.lane][self.index - 1].turned == 1):
                        self.y -= self.speed
                else:
                    if self.turned == 0:
                        self.rotateAngle += rotationAngle
                        self.image = pygame.transform.rotate(self.originalImage, -self.rotateAngle)
                        self.x += 1
                        self.y -= 1
                        if self.rotateAngle == 90:
                            self.turned = 1
                            vehiclesTurned[self.direction][self.lane].append(self)
                            self.crossedIndex = len(vehiclesTurned[self.direction][self.lane]) - 1
                    else:
                        if self.crossedIndex == 0 or (self.x < (vehiclesTurned[self.direction][self.lane][self.crossedIndex - 1].x - vehiclesTurned[self.direction][self.lane][self.crossedIndex - 1].image.get_rect().width - movingGap)):
                            self.x += self.speed

# Initialization of signals
def initialize():
    global signals, currentGroup
    ts0 = TrafficSignal(0, defaultYellow, defaultGreen[0])  # right
    ts2 = TrafficSignal(0, defaultYellow, defaultGreen[2])  # left
    ts3 = TrafficSignal(0, defaultYellow, defaultGreen[3])  # up
    signals = {0: ts0, 2: ts2, 3: ts3}

    signals[0].red = 0
    signals[2].red = 0
    signals[3].red = signals[0].green + signals[0].yellow
    currentGroup = 0
    t = threading.Thread(target=repeat, name="signal_control", daemon=True)
    t.start()

# Print the signal timers on cmd
def printStatus():
    for i in sorted(signals.keys()):
        grp = 0 if i in (0, 2) else 1
        state = ""
        if grp == currentGroup:
            state = "GREEN" if currentYellow == 0 else "YELLOW"
        else:
            state = "RED"
        print(f"{state:>6} TS {i} -> r: {signals[i].red}, y: {signals[i].yellow}, g: {signals[i].green} (Default: {defaultGreen[i]})")
    print()

# Main signal control loop
def repeat():
    global currentGroup, currentYellow, total_flow_count, count_Leg1, count_Leg3, count_Leg4
    group_dirs = {0: (0, 2), 1: (3,)}

    while True:
        dirs = group_dirs[currentGroup]
        
        if prediction_model_mode:
            k = total_flow_count or 1
            group_flow = (count_Leg1 + count_Leg3) / k if currentGroup == 0 else count_Leg4 / k
            
            adjustment_factor = ml_model_adjustment_factor(group_flow)
            min_green, max_green = 3, 25

            for d in dirs:
                base_green = defaultGreen[d]
                new_green_time = int(max(min_green, min(max_green, base_green * adjustment_factor)))
                signals[d].green = new_green_time
        else:
            for d in dirs:
                signals[d].green = defaultGreen[d]

        group_green_time = signals[dirs[0]].green
        currentYellow = 0
        other_group = 1 - currentGroup
        other_dirs = group_dirs[other_group]
        for d in other_dirs:
            signals[d].red = group_green_time + defaultYellow

        while signals[dirs[0]].green > 0:
            # printStatus()
            updateValues()
            time.sleep(1)

        currentYellow = 1
        for d in dirs:
            signals[d].yellow = defaultYellow
        
        for d in dirs:
            for i in range(0, 3):
                for vehicle in vehicles[directionNumbers[d]][i]:
                    vehicle.stop = defaultStop[directionNumbers[d]]

        while signals[dirs[0]].yellow > 0:
            # printStatus()
            updateValues()
            time.sleep(1)

        currentYellow = 0
        for d in dirs:
            signals[d].yellow = defaultYellow

        currentGroup = 1 - currentGroup

# Update signal timers every second
def updateValues():
    group_dirs = {0: (0, 2), 1: (3,)}
    try:
        active_dirs = group_dirs[currentGroup]
        other_dirs = group_dirs[1 - currentGroup]

        if currentYellow == 1:
            for d in active_dirs:
                if signals[d].yellow > 0: signals[d].yellow -= 1
        else:
            for d in active_dirs:
                if signals[d].green > 0: signals[d].green -= 1

        for d in other_dirs:
            if signals[d].red > 0: signals[d].red -= 1
    except Exception as e:
        print(f"updateValues error: {e}")


# Generating vehicles
def generateVehicles():
    global total_flow_count, count_Leg1, count_Leg3, count_Leg4
    while True:
        vehicle_type = random.choice(allowedVehicleTypesList)
        lane_number = random.randint(1, 2)
        will_turn = 0 # Mặc định là đi thẳng

        temp = random.randint(0, 99)
        direction_number = 0
        if temp < 10:
            direction_number = 3  # south to north (Up)
            count_Leg4 += 1
        elif temp < 55:
            direction_number = 0  # west to east (Right)
            count_Leg1 += 1
            if random.randint(0, 99) < 40: will_turn = 1
        else:
            direction_number = 2  # east to west  (Left)
            count_Leg3 += 1
            if random.randint(0, 99) < 40: will_turn = 1
        
        # THAY ĐỔI QUAN TRỌNG: Bắt buộc xe từ hướng 'up' phải rẽ.
        if direction_number == 3:
            will_turn = 1

        Vehicle(
            lane_number,
            vehicleTypes[vehicle_type],
            direction_number,
            directionNumbers[direction_number],
            will_turn,
        )
        time.sleep(1.25)
        total_flow_count += 1


def showStats():
    totalVehicles = 0
    print("\n--- SIMULATION STATS ---")
    print("Direction-wise Vehicle crossed Counts:")
    for i in active_directions:
        print(f"- Direction '{directionNumbers[i]}': {vehicles[directionNumbers[i]]['crossed']}")
        totalVehicles += vehicles[directionNumbers[i]]["crossed"]
    print(f"\nTotal vehicles passed: {totalVehicles}")
    print(f"Total time elapsed: {timeElapsed} seconds")
    print("------------------------\n")


def simTime():
    global timeElapsed, simulationTime
    while True:
        timeElapsed += 1
        time.sleep(1)
        if timeElapsed == simulationTime and simulationTime != 0:
            showStats()
            os._exit(1)


class Main:
    # Setup allowed vehicle types
    for i, (vehicleType, allowed) in enumerate(allowedVehicleTypes.items()):
        if allowed:
            allowedVehicleTypesList.append(i)

    thread1 = threading.Thread(name="initialization", target=initialize, args=())
    thread1.daemon = True
    thread1.start()

    # Pygame setup
    black, white = (0, 0, 0), (255, 255, 255)
    screenWidth, screenHeight = 1400, 800
    screen = pygame.display.set_mode((screenWidth, screenHeight))
    pygame.display.set_caption("T-Intersection Traffic Simulation")

    # Load assets
    background = pygame.image.load("./images/intersection2.png") # Consider using a T-intersection image
    redSignal = pygame.image.load("./images/signals/red.png")
    yellowSignal = pygame.image.load("./images/signals/yellow.png")
    greenSignal = pygame.image.load("./images/signals/green.png")
    font = pygame.font.Font(None, 30)

    # Start simulation threads
    thread2 = threading.Thread(name="generateVehicles", target=generateVehicles, args=())
    thread2.daemon = True
    thread2.start()

    thread3 = threading.Thread(name="simTime", target=simTime, args=())
    thread3.daemon = True
    thread3.start()

    # Main game loop
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                showStats()
                sys.exit()

        screen.blit(background, (0, 0))

        # Display signals and timers
        for i in active_directions:
            display_idx = display_idx_map[i]
            grp = 0 if i in (0, 2) else 1
            
            if grp == currentGroup:
                if currentYellow == 1:
                    signals[i].signalText = signals[i].yellow
                    screen.blit(yellowSignal, signalCoods[display_idx])
                else:
                    signals[i].signalText = signals[i].green
                    screen.blit(greenSignal, signalCoods[display_idx])
            else:
                signals[i].signalText = signals[i].red
                screen.blit(redSignal, signalCoods[display_idx])
            
            timer_text = font.render(str(signals[i].signalText), True, white, black)
            screen.blit(timer_text, signalTimerCoods[display_idx])

        # Display vehicles
        for vehicle in simulation:
            screen.blit(vehicle.image, [vehicle.x, vehicle.y])
            vehicle.move()

        # Display crossed vehicle counts
        for i, direction_id in enumerate(active_directions):
            count_text = f"{directionNumbers[direction_id].capitalize()}: {vehicles[directionNumbers[direction_id]]['crossed']}"
            text_surface = font.render(count_text, True, black, white)
            screen.blit(text_surface, (1150, 70 + i * 40))
        
        # Display time
        time_text = font.render(f"Time Elapsed: {timeElapsed}", True, black, white)
        screen.blit(time_text, (1150, 30))

        pygame.display.update()


if __name__ == "__main__":
    Main()