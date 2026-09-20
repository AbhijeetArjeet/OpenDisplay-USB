"""Synthetic video frame generator for testing without a virtual display."""

import numpy as np
from PIL import Image, ImageDraw, ImageFont


class TestPatternGenerator:
    """Generates synthetic RGB frames with animation and timestamps."""

    def __init__(self, width: int = 1920, height: int = 1080):
        self.width = width
        self.height = height
        self.ball_x = 100
        self.ball_y = 100
        self.speed_x = 8
        self.speed_y = 6
        self.ball_radius = 40
        self.frame_num = 0

    def generate_frame(self) -> np.ndarray:
        """Renders one RGB test frame."""
        img = Image.new("RGB", (self.width, self.height), color=(20, 24, 30))
        draw = ImageDraw.Draw(img)

        # Draw grid
        grid_step = 80
        for x in range(0, self.width, grid_step):
            draw.line([(x, 0), (x, self.height)], fill=(40, 48, 60), width=1)
        for y in range(0, self.height, grid_step):
            draw.line([(0, y), (self.width, y)], fill=(40, 48, 60), width=1)

        # Animate bouncing ball
        self.ball_x += self.speed_x
        self.ball_y += self.speed_y

        if self.ball_x - self.ball_radius < 0 or self.ball_x + self.ball_radius >= self.width:
            self.speed_x = -self.speed_x
        if self.ball_y - self.ball_radius < 0 or self.ball_y + self.ball_radius >= self.height:
            self.speed_y = -self.speed_y

        draw.ellipse(
            [
                (self.ball_x - self.ball_radius, self.ball_y - self.ball_radius),
                (self.ball_x + self.ball_radius, self.ball_y + self.ball_radius)
            ],
            fill=(76, 175, 80),
            outline=(255, 255, 255),
            width=2
        )

        # Draw text stats
        text = f"OpenDisplay USB Test Stream - Frame {self.frame_num} ({self.width}x{self.height})"
        draw.text((40, 40), text, fill=(255, 255, 255))

        self.frame_num += 1
        return np.array(img)
