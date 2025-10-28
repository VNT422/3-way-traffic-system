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

# load your ML model (file must exist)
# mj = joblib.load("model_joblib")  # mj => model joblib
# Tạo một mô hình giả lập nếu bạn không có file "model_joblib"
class MockModel:
    def predict(self, flow_percentile):
        # Mô hình giả lập giờ đây trả về một HỆ SỐ ĐIỀU CHỈNH
        # Thay vì thời gian đèn xanh tuyệt đối.
        # Ví dụ: nếu flow_percentile là 0, hệ số là 0.7 (giảm 30%)
        # nếu flow_percentile là 100, hệ số là 1.3 (tăng 30%)
        # Đảm bảo flow_percentile được chuẩn hóa hoặc xử lý phù hợp.
        # Ở đây, giả định flow_percentile là giá trị thực tế của lưu lượng.
        
        # Chúng ta sẽ tính toán một hệ số dựa trên lưu lượng:
        # Giả sử lưu lượng cao hơn (ví dụ > 50) sẽ làm tăng green time, lưu lượng thấp hơn sẽ giảm
        
        # Chuyển đổi flow_percentile thành một con số đơn
        if isinstance(flow_percentile, np.ndarray) and flow_percentile.size > 0:
            current_flow = flow_percentile.item() if flow_percentile.ndim == 0 else flow_percentile[0][0]
        else:
            current_flow = 0 # Hoặc một giá trị mặc định hợp lý

        # Ví dụ đơn giản:
        # Nếu lưu lượng < 20, hệ số ~0.8
        # Nếu lưu lượng ~ 50, hệ số ~1.0
        # Nếu lưu lượng > 80, hệ số ~1.2
        
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


# Default values of signal timers - BẠN ĐIỀU CHỈNH CÁC GIÁ TRỊ NÀY TRỰC TIẾP
a0=12-2
a1=12-2
a2=12-2
a3=12-2
a4=15-2
defaultGreen = {0: a0, 1: a1, 2: a2, 3: a3} # VÍ DỤ: {0: 18, 1: 12, 2: 18, 3: 12}
defaultRed = a4
defaultYellow = 3

signals = []
noOfSignals = 4
currentGreen = 0  # Indicates which signal is green currently

nextGreen = (currentGreen + 1) % noOfSignals

currentYellow = 0  # 0 -> green phase, 1 -> yellow phase

signal_states = ["red"] * noOfSignals
signal_lock = threading.Lock()

speeds = {"car": 2.25, "bus": 1.8, "truck": 1.8, "bike": 2.5}


# Coordinates of vehicles' start
x = {
    "right": [0, 0, 0],
    "down": [542, 563, 637],
    "left": [1400, 1400, 1400],
    "up": [680, 723, 819],
}
y = {
    "right": [380, 410, 465],
    "down": [0, 0, 0],
    "left": [258, 315, 365],
    "up": [800, 800, 800],
}

vehicles = {
    "right": {0: [], 1: [], 2: [], "crossed": 0},
    "down": {0: [], 1: [], 2: [], "crossed": 0},
    "left": {0: [], 1: [], 2: [], "crossed": 0},
    "up": {0: [], 1: [], 2: [], "crossed": 0},
}
vehicleTypes = {0: "car", 1: "bus", 2: "truck", 3: "bike"}
directionNumbers = {0: "right", 1: "down", 2: "left", 3: "up"}

signalCoods = [(300, 600), (300, 110), (1070, 100), (1070, 610)]
signalTimerCoods = [(300, 600), (300, 110), (1070, 100), (1070, 610)]

stopLines = {"right": 350, "down": 197, "left": 1050, "up": 603}
defaultStop = {"right": 340, "down": 187, "left": 1060, "up": 610}

stoppingGap = 25
movingGap = 30

allowedVehicleTypes = {"car": True, "bus": True, "truck": True, "bike": True}

allowedVehicleTypesList = []

vehiclesTurned = {
    "right": {1: [], 2: []},
    "down": {1: [], 2: []},
    "left": {1: [], 2: []},
    "up": {1: [], 2: []},
}
vehiclesNotTurned = {
    "right": {1: [], 2: []},
    "down": {1: [], 2: []},
    "left": {1: [], 2: []},
    "up": {1: [], 2: []},
}

rotationAngle = 3

mid = {
    "right": {"x": 560, "y": 465},
    "down": {"x": 560, "y": 310},
    "left": {"x": 860, "y": 310},
    "up": {"x": 815, "y": 495},
}

randomGreenSignalTimer = False
randomGreenSignalTimerRange = [10, 20]

timeElapsed = 0
simulationTime = 0  # 0 for infinite simulation time
timeElapsedCoods = (1050, 30)

vehicleCountTexts = ["0", "0", "0", "0"]
vehicleCountCoods = [(1050, 70), (1050, 110), (1050, 150), (1050, 190)]

count_Leg1 = 0
count_Leg2 = 0
count_Leg3 = 0
count_Leg4 = 0

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
        # self.vehicleClass = vehicleClass
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
                    - vehicles[direction][lane][self.index - 1]
                    .image.get_rect()
                    .width
                    - stoppingGap
                )
            elif direction == "left":
                self.stop = (
                    vehicles[direction][lane][self.index - 1].stop
                    + vehicles[direction][lane][self.index - 1]
                    .image.get_rect()
                    .width
                    + stoppingGap
                )
            elif direction == "down":
                self.stop = (
                    vehicles[direction][lane][self.index - 1].stop
                    - vehicles[direction][lane][self.index - 1]
                    .image.get_rect()
                    .height
                    - stoppingGap
                )
            elif direction == "up":
                self.stop = (
                    vehicles[direction][lane][self.index - 1].stop
                    + vehicles[direction][lane][self.index - 1]
                    .image.get_rect()
                    .height
                    + stoppingGap
                )
        else:
            self.stop = defaultStop[direction]

        # Set new starting and stopping coordinate
        if direction == "right":
            temp = self.image.get_rect().width + stoppingGap
            x[direction][lane] -= temp
        elif direction == "left":
            temp = self.image.get_rect().width + stoppingGap
            x[direction][lane] += temp
        elif direction == "down":
            temp = self.image.get_rect().height + stoppingGap
            y[direction][lane] -= temp
        elif direction == "up":
            temp = self.image.get_rect().height + stoppingGap
            y[direction][lane] += temp
        simulation.add(self)

    def render(self, screen):
        screen.blit(self.image, (self.x, self.y))

    def move(self):
        # NOTE: only changed conditions to support opposite-direction green
        # group mapping:
        # group 0 (0 & 2) -> directions right (0) and left (2)
        # group 1 (1 & 3) -> directions down (1) and up (3)

        if self.direction == "right":
            if (
                self.crossed == 0
                and self.x + self.image.get_rect().width > stopLines[self.direction]
            ):
                self.crossed = 1
                vehicles[self.direction]["crossed"] += 1
                if self.willTurn == 0:
                    vehiclesNotTurned[self.direction][self.lane].append(self)
                    self.crossedIndex = (
                        len(vehiclesNotTurned[self.direction][self.lane]) - 1
                    )
            if self.willTurn == 1:
                if self.lane == 1:
                    if (
                        self.crossed == 0
                        or self.x + self.image.get_rect().width
                        < stopLines[self.direction] + 365
                    ):
                        # CHANGED: allow either currentGreen==0 OR currentGreen==2
                        if (
                            self.x + self.image.get_rect().width <= self.stop
                            or ((currentGreen == 0 or currentGreen == 2) and currentYellow == 0)
                            or self.crossed == 1
                        ) and (
                            self.index == 0
                            or self.x + self.image.get_rect().width
                            < (
                                vehicles[self.direction][self.lane][self.index - 1].x
                                - movingGap
                            )
                            or vehicles[self.direction][self.lane][
                                self.index - 1
                            ].turned
                            == 1
                        ):
                            self.x += self.speed
                    else:
                        if self.turned == 0:
                            self.rotateAngle += rotationAngle
                            self.image = pygame.transform.rotate(
                                self.originalImage, self.rotateAngle
                            )
                            self.x += 2.4
                            self.y -= 2.8
                            if self.rotateAngle == 90:
                                self.turned = 1
                                vehiclesTurned[self.direction][self.lane].append(self)
                                self.crossedIndex = (
                                    len(vehiclesTurned[self.direction][self.lane]) - 1
                                )
                        else:
                            if self.crossedIndex == 0 or (
                                self.y
                                > (
                                    vehiclesTurned[self.direction][self.lane][
                                        self.crossedIndex - 1
                                    ].y
                                    + vehiclesTurned[self.direction][self.lane][
                                        self.crossedIndex - 1
                                    ]
                                    .image.get_rect()
                                    .height
                                    + movingGap
                                )
                            ):
                                self.y -= self.speed
                elif self.lane == 2:
                    if (
                        self.crossed == 0
                        or self.x + self.image.get_rect().width
                        < mid[self.direction]["x"]
                    ):
                        if (
                            self.x + self.image.get_rect().width <= self.stop
                            or ((currentGreen == 0 or currentGreen == 2) and currentYellow == 0)
                            or self.crossed == 1
                        ) and (
                            self.index == 0
                            or self.x + self.image.get_rect().width
                            < (
                                vehicles[self.direction][self.lane][self.index - 1].x
                                - movingGap
                            )
                            or vehicles[self.direction][self.lane][
                                self.index - 1
                            ].turned
                            == 1
                        ):
                            self.x += self.speed
                    else:
                        if self.turned == 0:
                            self.rotateAngle += rotationAngle
                            self.image = pygame.transform.rotate(
                                self.originalImage, -self.rotateAngle
                            )
                            self.x += 2
                            self.y += 1.8
                            if self.rotateAngle == 90:
                                self.turned = 1
                                vehiclesTurned[self.direction][self.lane].append(self)
                            self.crossedIndex = (
                                len(vehiclesTurned[self.direction][self.lane]) - 1
                            )
                        else:
                            if self.crossedIndex == 0 or (
                                (self.y + self.image.get_rect().height)
                                < (
                                    vehiclesTurned[self.direction][self.lane][
                                        self.crossedIndex - 1
                                    ].y
                                    - movingGap
                                )
                            ):
                                self.y += self.speed
            else:
                if self.crossed == 0:
                    if (
                        self.x + self.image.get_rect().width <= self.stop
                        or ((currentGreen == 0 or currentGreen == 2) and currentYellow == 0)
                    ) and (
                        self.index == 0
                        or self.x + self.image.get_rect().width
                        < (
                            vehicles[self.direction][self.lane][self.index - 1].x
                            - movingGap
                        )
                    ):
                        self.x += self.speed
                else:
                    if (self.crossedIndex == 0) or (
                        self.x + self.image.get_rect().width
                        < (
                            vehiclesNotTurned[self.direction][self.lane][
                                self.crossedIndex - 1
                            ].x
                            - movingGap
                        )
                    ):
                        self.x += self.speed

        elif self.direction == "down":
            if (
                self.crossed == 0
                and self.y + self.image.get_rect().height > stopLines[self.direction]
            ):
                self.crossed = 1
                vehicles[self.direction]["crossed"] += 1
                if self.willTurn == 0:
                    vehiclesNotTurned[self.direction][self.lane].append(self)
                    self.crossedIndex = (
                        len(vehiclesNotTurned[self.direction][self.lane]) - 1
                    )
            if self.willTurn == 1:
                if self.lane == 2:
                    if (
                        self.crossed == 0
                        or self.y + self.image.get_rect().height
                        < stopLines[self.direction] + 210
                    ):
                        # CHANGED: allow group (1 or 3)
                        if (
                            self.y + self.image.get_rect().height <= self.stop
                            or ((currentGreen == 1 or currentGreen == 3) and currentYellow == 0)
                            or self.crossed == 1
                        ) and (
                            self.index == 0
                            or self.y + self.image.get_rect().height
                            < (
                                vehicles[self.direction][self.lane][self.index - 1].y
                                - movingGap
                            )
                            or vehicles[self.direction][self.lane][
                                self.index - 1
                            ].turned
                            == 1
                        ):
                            self.y += self.speed
                    else:
                        if self.turned == 0:
                            self.rotateAngle += rotationAngle
                            self.image = pygame.transform.rotate(
                                self.originalImage, self.rotateAngle
                            )
                            self.x += 1.2
                            self.y += 1.8
                            if self.rotateAngle == 90:
                                self.turned = 1
                                vehiclesTurned[self.direction][self.lane].append(self)
                                self.crossedIndex = (
                                    len(vehiclesTurned[self.direction][self.lane]) - 1
                                )
                        else:
                            if self.crossedIndex == 0 or (
                                (self.x + self.image.get_rect().width)
                                < (
                                    vehiclesTurned[self.direction][self.lane][
                                        self.crossedIndex - 1
                                    ].x
                                    - movingGap
                                )
                            ):
                                self.x += self.speed
                elif self.lane == 1:
                    if (
                        self.crossed == 0
                        or self.y + self.image.get_rect().height
                        < mid[self.direction]["y"]
                    ):
                        if (
                            self.y + self.image.get_rect().height <= self.stop
                            or ((currentGreen == 1 or currentGreen == 3) and currentYellow == 0)
                            or self.crossed == 1
                        ) and (
                            self.index == 0
                            or self.y + self.image.get_rect().height
                            < (
                                vehicles[self.direction][self.lane][self.index - 1].y
                                - movingGap
                            )
                            or vehicles[self.direction][self.lane][
                                self.index - 1
                            ].turned
                            == 1
                        ):
                            self.y += self.speed
                    else:
                        if self.turned == 0:
                            self.rotateAngle += rotationAngle
                            self.image = pygame.transform.rotate(
                                self.originalImage, -self.rotateAngle
                            )
                            self.x -= 2.5
                            self.y += 2
                            if self.rotateAngle == 90:
                                self.turned = 1
                                vehiclesTurned[self.direction][self.lane].append(self)
                                self.crossedIndex = (
                                    len(vehiclesTurned[self.direction][self.lane]) - 1
                                )
                        else:
                            if self.crossedIndex == 0 or (
                                self.x
                                > (
                                    vehiclesTurned[self.direction][self.lane][
                                        self.crossedIndex - 1
                                    ].x
                                    + vehiclesTurned[self.direction][self.lane][
                                        self.crossedIndex - 1
                                    ]
                                    .image.get_rect()
                                    .width
                                    + movingGap
                                )
                            ):
                                self.x -= self.speed
            else:
                if self.crossed == 0:
                    if (
                        self.y + self.image.get_rect().height <= self.stop
                        or ((currentGreen == 1 or currentGreen == 3) and currentYellow == 0)
                    ) and (
                        self.index == 0
                        or self.y + self.image.get_rect().height
                        < (
                            vehicles[self.direction][self.lane][self.index - 1].y
                            - movingGap
                        )
                    ):
                        self.y += self.speed
                else:
                    if (self.crossedIndex == 0) or (
                        self.y + self.image.get_rect().height
                        < (
                            vehiclesNotTurned[self.direction][self.lane][
                                self.crossedIndex - 1
                            ].y
                            - movingGap
                        )
                    ):
                        self.y += self.speed

        elif self.direction == "left":
            if self.crossed == 0 and self.x < stopLines[self.direction]:
                self.crossed = 1
                vehicles[self.direction]["crossed"] += 1
                if self.willTurn == 0:
                    vehiclesNotTurned[self.direction][self.lane].append(self)
                    self.crossedIndex = (
                        len(vehiclesNotTurned[self.direction][self.lane]) - 1
                    )
            if self.willTurn == 1:
                if self.lane == 2:
                    if self.crossed == 0 or self.x > stopLines[self.direction] - 440:
                        if (
                            self.x >= self.stop
                            or ((currentGreen == 0 or currentGreen == 2) and currentYellow == 0)
                            or self.crossed == 1
                        ) and (
                            self.index == 0
                            or self.x
                            > (
                                vehicles[self.direction][self.lane][self.index - 1].x
                                + vehicles[self.direction][self.lane][self.index - 1]
                                .image.get_rect()
                                .width
                                + movingGap
                            )
                            or vehicles[self.direction][self.lane][
                                self.index - 1
                            ].turned
                            == 1
                        ):
                            self.x -= self.speed
                    else:
                        if self.turned == 0:
                            self.rotateAngle += rotationAngle
                            self.image = pygame.transform.rotate(
                                self.originalImage, self.rotateAngle
                            )
                            self.x -= 1
                            self.y += 1.2
                            if self.rotateAngle == 90:
                                self.turned = 1
                                vehiclesTurned[self.direction][self.lane].append(self)
                                self.crossedIndex = (
                                    len(vehiclesTurned[self.direction][self.lane]) - 1
                                )
                        else:
                            if self.crossedIndex == 0 or (
                                (self.y + self.image.get_rect().height)
                                < (
                                    vehiclesTurned[self.direction][self.lane][
                                        self.crossedIndex - 1
                                    ].y
                                    - movingGap
                                )
                            ):
                                self.y += self.speed
                elif self.lane == 1:
                    if self.crossed == 0 or self.x > mid[self.direction]["x"]:
                        if (
                            self.x >= self.stop
                            or ((currentGreen == 0 or currentGreen == 2) and currentYellow == 0)
                            or self.crossed == 1
                        ) and (
                            self.index == 0
                            or self.x
                            > (
                                vehicles[self.direction][self.lane][self.index - 1].x
                                + vehicles[self.direction][self.lane][self.index - 1]
                                .image.get_rect()
                                .width
                                + movingGap
                            )
                            or vehicles[self.direction][self.lane][
                                self.index - 1
                            ].turned
                            == 1
                        ):
                            self.x -= self.speed
                    else:
                        if self.turned == 0:
                            self.rotateAngle += rotationAngle
                            self.image = pygame.transform.rotate(
                                self.originalImage, -self.rotateAngle
                            )
                            self.x -= 1.8
                            self.y -= 2.5
                            if self.rotateAngle == 90:
                                self.turned = 1
                                vehiclesTurned[self.direction][self.lane].append(self)
                                self.crossedIndex = (
                                    len(vehiclesTurned[self.direction][self.lane]) - 1
                                )
                        else:
                            if self.crossedIndex == 0 or (
                                self.y
                                > (
                                    vehiclesTurned[self.direction][self.lane][
                                        self.crossedIndex - 1
                                    ].y
                                    + vehiclesTurned[self.direction][self.lane][
                                        self.crossedIndex - 1
                                    ]
                                    .image.get_rect()
                                    .height
                                    + movingGap
                                )
                            ):
                                self.y -= self.speed
            else:
                if self.crossed == 0:
                    if (
                        self.x >= self.stop
                        or ((currentGreen == 0 or currentGreen == 2) and currentYellow == 0)
                    ) and (
                        self.index == 0
                        or self.x
                        > (
                            vehicles[self.direction][self.lane][self.index - 1].x
                            + vehicles[self.direction][self.lane][self.index - 1]
                            .image.get_rect()
                            .width
                            + movingGap
                        )
                    ):
                        self.x -= self.speed
                else:
                    if (self.crossedIndex == 0) or (
                        self.x
                        > (
                            vehiclesNotTurned[self.direction][self.lane][
                                self.crossedIndex - 1
                            ].x
                            + vehiclesNotTurned[self.direction][self.lane][
                                self.crossedIndex - 1
                            ]
                            .image.get_rect()
                            .width
                            + movingGap
                        )
                    ):
                        self.x -= self.speed

        elif self.direction == "up":
            if self.crossed == 0 and self.y < stopLines[self.direction]:
                self.crossed = 1
                vehicles[self.direction]["crossed"] += 1
                if self.willTurn == 0:
                    vehiclesNotTurned[self.direction][self.lane].append(self)
                    self.crossedIndex = (
                        len(vehiclesNotTurned[self.direction][self.lane]) - 1
                    )
            if self.willTurn == 1:
                if self.lane == 1:
                    if self.crossed == 0 or self.y > stopLines[self.direction] - 200:
                        if (
                            self.y >= self.stop
                            or ((currentGreen == 1 or currentGreen == 3) and currentYellow == 0)
                            or self.crossed == 1
                        ) and (
                            self.index == 0
                            or self.y
                            > (
                                vehicles[self.direction][self.lane][self.index - 1].y
                                + vehicles[self.direction][self.lane][self.index - 1]
                                .image.get_rect()
                                .height
                                + movingGap
                            )
                            or vehicles[self.direction][self.lane][
                                self.index - 1
                            ].turned
                            == 1
                        ):
                            self.y -= self.speed
                    else:
                        if self.turned == 0:
                            self.rotateAngle += rotationAngle
                            self.image = pygame.transform.rotate(
                                self.originalImage, self.rotateAngle
                            )
                            self.x -= 2
                            self.y -= 1.2
                            if self.rotateAngle == 90:
                                self.turned = 1
                                vehiclesTurned[self.direction][self.lane].append(self)
                                self.crossedIndex = (
                                    len(vehiclesTurned[self.direction][self.lane]) - 1
                                )
                        else:
                            if self.crossedIndex == 0 or (
                                self.x
                                > (
                                    vehiclesTurned[self.direction][self.lane][
                                        self.crossedIndex - 1
                                    ].x
                                    + vehiclesTurned[self.direction][self.lane][
                                        self.crossedIndex - 1
                                    ]
                                    .image.get_rect()
                                    .width
                                    + movingGap
                                )
                            ):
                                self.x -= self.speed
                elif self.lane == 2:
                    if self.crossed == 0 or self.y > mid[self.direction]["y"]:
                        if (
                            self.y >= self.stop
                            or ((currentGreen == 1 or currentGreen == 3) and currentYellow == 0)
                            or self.crossed == 1
                        ) and (
                            self.index == 0
                            or self.y
                            > (
                                vehicles[self.direction][self.lane][self.index - 1].y
                                + vehicles[self.direction][self.lane][self.index - 1]
                                .image.get_rect()
                                .height
                                + movingGap
                            )
                            or vehicles[self.direction][self.lane][
                                self.index - 1
                            ].turned
                            == 1
                        ):
                            self.y -= self.speed
                    else:
                        if self.turned == 0:
                            self.rotateAngle += rotationAngle
                            self.image = pygame.transform.rotate(
                                self.originalImage, -self.rotateAngle
                            )
                            self.x += 1
                            self.y -= 1
                            if self.rotateAngle == 90:
                                self.turned = 1
                                vehiclesTurned[self.direction][self.lane].append(self)
                                self.crossedIndex = (
                                    len(vehiclesTurned[self.direction][self.lane]) - 1
                                )
                        else:
                            if self.crossedIndex == 0 or (
                                self.x
                                < (
                                    vehiclesTurned[self.direction][self.lane][
                                        self.crossedIndex - 1
                                    ].x
                                    - vehiclesTurned[self.direction][self.lane][
                                        self.crossedIndex - 1
                                    ]
                                    .image.get_rect()
                                    .width
                                    - movingGap
                                )
                            ):
                                self.x += self.speed
            else:
                if self.crossed == 0:
                    if (
                        self.y >= self.stop
                        or ((currentGreen == 1 or currentGreen == 3) and currentYellow == 0)
                    ) and (
                        self.index == 0
                        or self.y
                        > (
                            vehicles[self.direction][self.lane][self.index - 1].y
                            + vehicles[self.direction][self.lane][self.index - 1]
                            .image.get_rect()
                            .height
                            + movingGap
                        )
                    ):
                        self.y -= self.speed
                else:
                    if (self.crossedIndex == 0) or (
                        self.y
                        > (
                            vehiclesNotTurned[self.direction][self.lane][
                                self.crossedIndex - 1
                            ].y
                            + vehiclesNotTurned[self.direction][self.lane][
                                self.crossedIndex - 1
                            ]
                            .image.get_rect()
                            .height
                            + movingGap
                        )
                    ):
                        self.y -= self.speed


# Initialization of signals with default values
def initialize():
    global signals, currentGroup, nextGroup, defaultGreen

    # Tạo các tín hiệu ban đầu dựa trên defaultGreen
    ts0 = TrafficSignal(0, defaultYellow, defaultGreen[0])  # right
    ts1 = TrafficSignal(0, defaultYellow, defaultGreen[1])  # down
    ts2 = TrafficSignal(0, defaultYellow, defaultGreen[2])  # left
    ts3 = TrafficSignal(0, defaultYellow, defaultGreen[3])  # up

    signals = [ts0, ts1, ts2, ts3]

    # Cập nhật trạng thái đèn đỏ ban đầu
    # Chúng ta sẽ bắt đầu với group 0 active (right+left green)
    signals[0].red = 0
    signals[2].red = 0
    signals[1].red = signals[1].yellow + signals[1].green
    signals[3].red = signals[3].yellow + signals[3].green

    # Bắt đầu vòng lặp dựa trên nhóm trong luồng riêng biệt
    currentGroup = 0
    nextGroup = 1
    t = threading.Thread(target=repeat, name="signal_control", daemon=True)
    t.start()


# Print the signal timers on cmd
def printStatus():
    for i in range(0, 4):
        if signals[i] != None:
            # determine group
            grp = 0 if i in (0, 2) else 1
            if grp == currentGroup:
                if currentYellow == 0:
                    print(
                        " GREEN TS",
                        i + 1,
                        "-> r:",
                        signals[i].red,
                        "-> y:",
                        signals[i].yellow,
                        "-> g:",
                        signals[i].green,
                        f"(Default: {defaultGreen[i]})" # Thêm thông tin defaultGreen
                    )
                else:
                    print(
                        "YELLOW TS",
                        i + 1,
                        "-> r:",
                        signals[i].red,
                        "-> y:",
                        signals[i].yellow,
                        "-> g:",
                        signals[i].green,
                        f"(Default: {defaultGreen[i]})" # Thêm thông tin defaultGreen
                    )
            else:
                print(
                    "   RED TS",
                    i + 1,
                    "-> r:",
                    signals[i].red,
                    "-> y:",
                    signals[i].yellow,
                    "-> g:",
                    signals[i].green,
                    f"(Default: {defaultGreen[i]})" # Thêm thông tin defaultGreen
                )
    print()


def repeat():
    global currentGroup, currentYellow, nextGreen, currentGreen, total_flow_count, count_Leg1, count_Leg2, count_Leg3, count_Leg4
    # helper mapping group -> direction indices
    group_dirs = {0: (0, 2), 1: (1, 3)}

    # We'll use currentGroup to indicate which opposing pair is active.
    while True:
        dirs = group_dirs[currentGroup]
        
        # === Cập nhật thời gian đèn xanh cho nhóm hiện tại ===
        # Lấy thời gian đèn xanh cơ bản từ defaultGreen
        base_green_time_dir0 = defaultGreen[dirs[0]]
        base_green_time_dir1 = defaultGreen[dirs[1]]

        if prediction_model_mode:
            # Tránh chia cho 0
            k = total_flow_count or 1
            
            # Tính toán hệ số điều chỉnh từ mô hình
            if currentGroup == 0: # right (0) and left (2)
                group_flow = (count_Leg1 + count_Leg3) / k
            else: # down (1) and up (3)
                group_flow = (count_Leg2 + count_Leg4) / k
            
            adjustment_factor = ml_model_adjustment_factor(group_flow)
            
            # Áp dụng hệ số điều chỉnh vào thời gian đèn xanh cơ bản
            # Giới hạn thời gian đèn xanh cuối cùng trong một khoảng hợp lý
            min_green = 3 # Thời gian đèn xanh tối thiểu
            max_green = 25 # Thời gian đèn xanh tối đa

            new_green_time_dir0 = int(max(min_green, min(max_green, base_green_time_dir0 * adjustment_factor)))
            new_green_time_dir1 = int(max(min_green, min(max_green, base_green_time_dir1 * adjustment_factor)))
            
            signals[dirs[0]].green = new_green_time_dir0
            signals[dirs[1]].green = new_green_time_dir1
        else:
            # Nếu prediction_model_mode là False, sử dụng trực tiếp defaultGreen
            signals[dirs[0]].green = base_green_time_dir0
            signals[dirs[1]].green = base_green_time_dir1

        group_green_time = signals[dirs[0]].green # Lấy thời gian đèn xanh đã được cập nhật

        # GREEN PHASE for the group
        currentYellow = 0
        currentGreen = dirs[0] # Cho tương thích với logic di chuyển xe

        # For the other group, set red equal to group_green_time + yellow of current
        other = 1 - currentGroup
        other_dirs = group_dirs[other]
        # Thời gian đèn đỏ của nhóm không hoạt động sẽ bằng thời gian đèn xanh của nhóm hiện tại + đèn vàng
        signals[other_dirs[0]].red = group_green_time + defaultYellow
        signals[other_dirs[1]].red = group_green_time + defaultYellow

        # Run green countdown
        while signals[dirs[0]].green > 0:
            printStatus()
            updateValues()
            time.sleep(1)

        # YELLOW PHASE for the group
        currentYellow = 1
        signals[dirs[0]].yellow = defaultYellow
        signals[dirs[1]].yellow = defaultYellow

        # reset stops for vehicles on the group (as original logic)
        for i in range(0, 3):
            for vehicle in vehicles[directionNumbers[dirs[0]]][i]:
                vehicle.stop = defaultStop[directionNumbers[dirs[0]]]
            for vehicle in vehicles[directionNumbers[dirs[1]]][i]:
                vehicle.stop = defaultStop[directionNumbers[dirs[1]]]

        while signals[dirs[0]].yellow > 0:
            printStatus()
            updateValues()
            time.sleep(1)

        # End of yellow: set currentYellow off
        currentYellow = 0

        # Reset yellows back to default for next cycle
        signals[dirs[0]].yellow = defaultYellow
        signals[dirs[1]].yellow = defaultYellow

        # switch group
        currentGroup = 1 - currentGroup
        nextGreen = (currentGroup + 1) % noOfSignals
        # continue loop; repeat()


# Update values of the signal timers after every second
def updateValues():
    # group-based update: active group reduces green/yellow; other group reduces red
    try:
        # find active group
        active_group = 0 if currentGroup == 0 else 1
        if active_group == 0:
            active_dirs = (0, 2)
            other_dirs = (1, 3)
        else:
            active_dirs = (1, 3)
            other_dirs = (0, 2)

        # active group: decrement green or yellow
        if currentYellow == 1:
            for d in active_dirs:
                if signals[d].yellow > 0:
                    signals[d].yellow -= 1
        else:
            for d in active_dirs:
                if signals[d].green > 0:
                    signals[d].green -= 1

        # other group: decrement red
        for d in other_dirs:
            if signals[d].red > 0:
                signals[d].red -= 1
    except Exception as e:
        print("updateValues error:", e)


# Generating vehicles in the simulation
def generateVehicles():
    global total_flow_count, count_Leg1, count_Leg2, count_Leg3, count_Leg4
    while True:
        vehicle_type = random.choice(allowedVehicleTypesList)
        lane_number = random.randint(1, 2)
        will_turn = 0

        if lane_number == 1:
            temp = random.randint(0, 99)
            if temp < 40:
                will_turn = 1
        elif lane_number == 2:
            temp = random.randint(0, 99)
            if temp < 40:
                will_turn = 1

        temp = random.randint(0, 100)

        direction_number = 0
        dist = [5, 11, 56, 101]
        if temp < dist[0]:
            direction_number = 1  # north to south (Down)
            count_Leg2 += 1
        elif temp < dist[1]:
            direction_number = 3  # south to north (Up)
            count_Leg4 += 1
        elif temp < dist[2]:
            direction_number = 0  # west to east (Right)
            count_Leg1 += 1
        elif temp < dist[3]:
            direction_number = 2  # east to west  (Left)
            count_Leg3 += 1
        Vehicle(
            lane_number,
            vehicleTypes[vehicle_type],
            direction_number,
            directionNumbers[direction_number],
            will_turn,
        )
        time.sleep(1.25)
        total_flow_count += 1
        # debug
        # print("Total flow count: ", total_flow_count)


def showStats():
    totalVehicles = 0
    print("Direction-wise Vehicle crossed Counts of Lanes#")
    for i in range(0, 4):
        if signals[i] != None:
            print("Direction", i + 1, ":", vehicles[directionNumbers[i]]["crossed"])
            totalVehicles += vehicles[directionNumbers[i]]["crossed"]
    print("Total vehicles passed: ", totalVehicles)
    print("Total time: ", timeElapsed)


def simTime():
    global timeElapsed, simulationTime
    while True:
        timeElapsed += 1
        time.sleep(1)
        if timeElapsed == simulationTime and simulationTime != 0:
            showStats()
            os._exit(1)


class Main:
    global allowedVehicleTypesList
    i = 0
    for vehicleType in allowedVehicleTypes:
        if allowedVehicleTypes[vehicleType]:
            allowedVehicleTypesList.append(i)
        i += 1
    thread1 = threading.Thread(name="initialization", target=initialize, args=())
    thread1.daemon = True
    thread1.start()

    # Colours
    black = (0, 0, 0)
    white = (255, 255, 255)

    # Screensize
    screenWidth = 1400
    screenHeight = 800
    screenSize = (screenWidth, screenHeight)

    background = pygame.image.load("./images/intersection2.png")
    screen = pygame.display.set_mode(screenSize)
    pygame.display.set_caption("SIMULATION")

    # Loading signal images and font
    redSignal = pygame.image.load("./images/signals/red.png")
    yellowSignal = pygame.image.load("./images/signals/yellow.png")
    greenSignal = pygame.image.load("./images/signals/green.png")
    font = pygame.font.Font(None, 28)
    thread2 = threading.Thread(name="generateVehicles1", target=generateVehicles, args=())
    thread2.daemon = True
    thread2.start()
    thread5 = threading.Thread(name="simTime", target=simTime, args=())
    thread5.daemon = True
    thread5.start()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                showStats()
                sys.exit()

        screen.blit(background, (0, 0))

        # display signals and timers
        for i in range(0, noOfSignals):
            if i in (0, 2):
                if currentGroup == 0:
                    if currentYellow == 1:
                        signals[i].signalText = signals[i].yellow
                        screen.blit(yellowSignal, signalCoods[i])
                    else:
                        signals[i].signalText = signals[i].green
                        screen.blit(greenSignal, signalCoods[i])
                else:
                    signals[i].signalText = signals[i].red
                    screen.blit(redSignal, signalCoods[i])
            else:  # i in (1,3)
                if currentGroup == 1:
                    if currentYellow == 1:
                        signals[i].signalText = signals[i].yellow
                        screen.blit(yellowSignal, signalCoods[i])
                    else:
                        signals[i].signalText = signals[i].green
                        screen.blit(greenSignal, signalCoods[i])
                else:
                    signals[i].signalText = signals[i].red
                    screen.blit(redSignal, signalCoods[i])

        # display signal timer
        for i in range(0, noOfSignals):
            txt = font.render(str(signals[i].signalText), True, white, black)
            screen.blit(txt, signalTimerCoods[i])

        # display the vehicles
        for vehicle in simulation:
            screen.blit(vehicle.image, [vehicle.x, vehicle.y])
            vehicle.move()

        # display vehicle count
        for i in range(0, noOfSignals):
            displayText = vehicles[directionNumbers[i]]["crossed"]
            vehicleCountTexts[i] = font.render(str(displayText), True, black, white)
            screen.blit(vehicleCountTexts[i], vehicleCountCoods[i])

        # display time elapsed
        timeElapsedText = font.render(("Time Elapsed: " + str(timeElapsed)), True, black, white)
        screen.blit(timeElapsedText, timeElapsedCoods)

        # display total_flow_count
        flowcount = font.render("Total flow count: " + str(total_flow_count), True, black, white)
        screen.blit(flowcount, totalflowcoods)

        pygame.display.update()


if __name__ == "__main__":
    Main() 