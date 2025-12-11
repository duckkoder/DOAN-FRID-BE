"""Face Verification Service for Face Registration.
Uses MediaPipe for face detection and pose estimation.
"""
import cv2
import mediapipe as mp
import numpy as np
import time
import base64
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class FaceVerificationService:
    """Service for real-time face verification during registration."""
    
    def __init__(self):
        """Initialize MediaPipe and verification settings."""
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.mp_drawing = mp.solutions.drawing_utils
        self.drawing_spec = self.mp_drawing.DrawingSpec(thickness=1, circle_radius=1)
        
        # 11 verification steps for comprehensive face capture
        self.verification_steps = [
            {
                "name": "face_front",
                "instruction": "Look straight at the camera for 1 second",
                "duration": 1.0,
                "condition": self.check_front_face,
                "tolerance": 10
            },
            # Left face angles (5°, 10°, 15°)
            {
                "name": "face_left_5",
                "instruction": "Turn your face slightly to the left (5°)",
                "duration": 1.0,
                "condition": self.check_left_face,
                "target_angle": 5,
                "tolerance": 4
            },
            {
                "name": "face_left_10",
                "instruction": "Turn your face to the left (10°)",
                "duration": 1.0,
                "condition": self.check_left_face,
                "target_angle": 10,
                "tolerance": 4
            },
            {
                "name": "face_left_15",
                "instruction": "Turn your face more to the left (15°)",
                "duration": 1.0,
                "condition": self.check_left_face,
                "target_angle": 15,
                "tolerance": 4
            },
            # Right face angles (5°, 10°, 15°)
            {
                "name": "face_right_5",
                "instruction": "Turn your face slightly to the right (5°)",
                "duration": 1.0,
                "condition": self.check_right_face,
                "target_angle": 5,
                "tolerance": 4
            },
            {
                "name": "face_right_10",
                "instruction": "Turn your face to the right (10°)",
                "duration": 1.0,
                "condition": self.check_right_face,
                "target_angle": 10,
                "tolerance": 4
            },
            {
                "name": "face_right_15",
                "instruction": "Turn your face more to the right (15°)",
                "duration": 1.0,
                "condition": self.check_right_face,
                "target_angle": 15,
                "tolerance": 4
            },
            # Face close
            {
                "name": "face_close",
                "instruction": "Move your face closer to the camera",
                "duration": 1.0,
                "condition": self.check_face_close,
                "tolerance": 5
            },
            # Face up/down (5° and 10°)
            {
                "name": "face_up_5",
                "instruction": "Tilt your face up (5°)",
                "duration": 1.0,
                "condition": self.check_up_face,
                "target_angle": -5,
                "tolerance": 4
            },
            {
                "name": "face_up_10",
                "instruction": "Tilt your face up more (10°)",
                "duration": 1.0,
                "condition": self.check_up_face,
                "target_angle": -10,
                "tolerance": 4
            },
            {
                "name": "face_down_5",
                "instruction": "Tilt your face down (5°)",
                "duration": 1.0,
                "condition": self.check_down_face,
                "target_angle": 5,
                "tolerance": 4
            },
            {
                "name": "face_down_10",
                "instruction": "Tilt your face down more (10°)",
                "duration": 1.0,
                "condition": self.check_down_face,
                "target_angle": 10,
                "tolerance": 4
            },
        ]
        
        # Session state
        self.current_step = 0
        self.step_start_time: Optional[float] = None
        self.face_width_history: List[int] = []
        
        # Flash effect
        self.flash_start_time: Optional[float] = None
        self.flash_duration = 0.3
        self.is_flashing = False
        
        # Captured images buffer (temporary storage before S3 upload)
        self.captured_images_buffer: List[Dict[str, Any]] = []
    
    def reset_session(self) -> None:
        """Reset verification session."""
        self.current_step = 0
        self.step_start_time = None
        self.face_width_history = []
        self.is_flashing = False
        self.captured_images_buffer = []
        logger.info("Face verification session reset")
    
    def get_current_step_info(self) -> Optional[Dict[str, Any]]:
        """Get current step information."""
        if self.current_step < len(self.verification_steps):
            return self.verification_steps[self.current_step]
        return None
    
    def is_completed(self) -> bool:
        """Check if all verification steps are completed."""
        return self.current_step >= len(self.verification_steps)
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current progress."""
        return {
            "current_step": self.current_step,
            "total_steps": len(self.verification_steps),
            "progress_percentage": round((self.current_step / len(self.verification_steps)) * 100, 2),
            "completed": self.is_completed()
        }
    
    def decode_base64_frame(self, base64_data: str) -> Optional[np.ndarray]:
        """Decode base64 image to numpy array."""
        try:
            # Remove data URL prefix if exists
            if ',' in base64_data:
                base64_data = base64_data.split(',')[1]
            
            img_data = base64.b64decode(base64_data)
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return frame
        except Exception as e:
            logger.error(f"Failed to decode base64 frame: {e}")
            return None
    
    def encode_frame_to_base64(self, frame: np.ndarray, quality: int = 80) -> str:
        """Encode numpy array to base64 JPEG."""
        try:
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
            img_str = base64.b64encode(buffer).decode()
            return f"data:image/jpeg;base64,{img_str}"
        except Exception as e:
            logger.error(f"Failed to encode frame: {e}")
            return ""
    
    def get_pose_estimation(self, image: np.ndarray, face_landmarks) -> Tuple[float, float, float]:
        """Estimate face pose angles (pitch, yaw, roll)."""
        img_h, img_w = image.shape[:2]
        face_3d = []
        face_2d = []
        
        # Key facial landmarks for pose estimation
        key_points = [33, 263, 1, 61, 291, 199]
        for idx in key_points:
            lm = face_landmarks.landmark[idx]
            x, y = int(lm.x * img_w), int(lm.y * img_h)
            face_2d.append([x, y])
            face_3d.append([x, y, lm.z])
        
        face_2d = np.array(face_2d, dtype=np.float64)
        face_3d = np.array(face_3d, dtype=np.float64)
        
        # Camera matrix
        focal_length = 1 * img_w
        cam_matrix = np.array([
            [focal_length, 0, img_w / 2],
            [0, focal_length, img_h / 2],
            [0, 0, 1]
        ])
        
        dist_matrix = np.zeros((4, 1), dtype=np.float64)
        
        # Solve PnP
        success, rot_vec, trans_vec = cv2.solvePnP(face_3d, face_2d, cam_matrix, dist_matrix)
        rmat, _ = cv2.Rodrigues(rot_vec)
        angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)
        
        # Convert to degrees
        x = -angles[0] * 360  # Pitch (up/down)
        y = -angles[1] * 360  # Yaw (left/right)
        z = angles[2] * 360   # Roll
        
        return x, y, z
    
    def get_face_bounding_box(self, face_landmarks, img_w: int, img_h: int) -> Tuple[int, int, int, int]:
        """Get face bounding box from landmarks."""
        x_coords = [lm.x * img_w for lm in face_landmarks.landmark]
        y_coords = [lm.y * img_h for lm in face_landmarks.landmark]
        
        x_min, x_max = int(min(x_coords)), int(max(x_coords))
        y_min, y_max = int(min(y_coords)), int(max(y_coords))
        
        width = x_max - x_min
        height = y_max - y_min
        
        return x_min, y_min, width, height
    
    def crop_face_image(
        self,
        image: np.ndarray,
        face_landmarks,
        img_w: int,
        img_h: int,
        padding: int = 8
    ) -> Tuple[Optional[np.ndarray], Tuple[int, int, int, int]]:
        """Crop face region with padding."""
        x_coords = [lm.x * img_w for lm in face_landmarks.landmark]
        y_coords = [lm.y * img_h for lm in face_landmarks.landmark]
        
        x_min = max(0, int(min(x_coords)) - padding)
        x_max = min(img_w, int(max(x_coords)) + padding)
        y_min = max(0, int(min(y_coords)) - padding)
        y_max = min(img_h, int(max(y_coords)) + padding)
        
        # Validate crop region
        if x_max <= x_min or y_max <= y_min:
            # Fallback: use nose landmark
            nose = face_landmarks.landmark[1]
            cx = int(nose.x * img_w)
            cy = int(nose.y * img_h)
            side = min(img_w, img_h) // 4
            x_min = max(0, cx - side // 2)
            x_max = min(img_w, cx + side // 2)
            y_min = max(0, cy - side // 2)
            y_max = min(img_h, cy + side // 2)
        
        face_crop = image[y_min:y_max, x_min:x_max].copy()
        crop_info = (x_min, y_min, x_max - x_min, y_max - y_min)
        
        return face_crop, crop_info
    
    # Condition check methods
    def check_front_face(self, x: float, y: float, z: float, step_info: Dict) -> bool:
        """Check if face is looking straight."""
        return abs(y) < step_info["tolerance"] and abs(x) < step_info["tolerance"]
    
    def check_left_face(self, x: float, y: float, z: float, step_info: Dict) -> bool:
        """Check if face is turned left to target angle."""
        target = step_info["target_angle"]
        tol = step_info["tolerance"]
        return target - tol < y < target + tol
    
    def check_right_face(self, x: float, y: float, z: float, step_info: Dict) -> bool:
        """Check if face is turned right to target angle."""
        target = -step_info["target_angle"]
        tol = step_info["tolerance"]
        return target - tol < y < target + tol
    
    def check_up_face(self, x: float, y: float, z: float, step_info: Dict) -> bool:
        """Check if face is tilted up to target angle."""
        target = step_info["target_angle"]  # Negative for up
        tol = step_info["tolerance"]
        return target - tol < x < target + tol
    
    def check_down_face(self, x: float, y: float, z: float, step_info: Dict) -> bool:
        """Check if face is tilted down to target angle."""
        target = step_info["target_angle"]  # Positive for down
        tol = step_info["tolerance"]
        return target - tol < x < target + tol
    
    def check_face_close(self, x: float, y: float, z: float, step_info: Dict) -> bool:
        """Check if face is close enough to camera."""
        if len(self.face_width_history) > 0:
            current_width = self.face_width_history[-1]
            return current_width > 200  # Minimum face width in pixels
        return False
    
    def draw_progress_bar(self, image: np.ndarray, progress: float) -> None:
        """Draw progress bar on image."""
        bar_width = 300
        bar_height = 20
        bar_x = 50
        bar_y = 100
        
        # Background
        cv2.rectangle(image, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height), (100, 100, 100), -1)
        
        # Progress
        progress_width = int(bar_width * progress)
        cv2.rectangle(image, (bar_x, bar_y), (bar_x + progress_width, bar_y + bar_height), (0, 255, 0), -1)
        
        # Border
        cv2.rectangle(image, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height), (255, 255, 255), 2)
    
    def trigger_flash(self) -> None:
        """Trigger flash effect."""
        self.flash_start_time = time.time()
        self.is_flashing = True
    
    def create_flash_effect(self, image: np.ndarray) -> np.ndarray:
        """Apply flash effect to image."""
        if self.is_flashing and self.flash_start_time:
            elapsed = time.time() - self.flash_start_time
            if elapsed < self.flash_duration:
                flash_intensity = 1.0 - (elapsed / self.flash_duration)
                flash_overlay = np.ones_like(image, dtype=np.uint8) * 255
                alpha = flash_intensity * 0.7
                image = cv2.addWeighted(image, 1 - alpha, flash_overlay, alpha, 0)
            else:
                self.is_flashing = False
        return image
    
    def process_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Process a single frame for face verification.
        NEW ARCHITECTURE: Return metadata only (no processed image).
        Client will draw bounding box and overlays on raw video stream.
        
        Returns:
            Dict containing:
                - current_step: current step number
                - total_steps: total number of steps
                - instruction: current instruction text
                - condition_met: whether pose condition is satisfied
                - progress: step progress (0-1)
                - face_detected: whether face is detected
                - pose_angles: dict with pitch, yaw, roll
                - bounding_box: dict with normalized x, y, width, height (0-1)
                - landmarks: list of 468 normalized (x, y, z) landmark points
                - should_capture: whether this frame should be captured
                - capture_data: captured image data if should_capture=True
        """
        # NO FLIP - keep original frame for processing
        # Client handles display mirroring if needed
        clean_image = frame.copy()
        
        # Process with MediaPipe
        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image_rgb.flags.writeable = False
        results = self.face_mesh.process(image_rgb)
        image_rgb.flags.writeable = True
        
        # Get frame dimensions for normalization
        img_h, img_w = frame.shape[:2]
        
        # Initialize result (NO processed_frame)
        result = {
            "current_step": self.current_step,
            "total_steps": len(self.verification_steps),
            "instruction": "",
            "condition_met": False,
            "progress": 0.0,
            "face_detected": False,
            "pose_angles": {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
            "bounding_box": None,
            "landmarks": None,
            "should_capture": False,
            "capture_data": None
        }
        
        if not results.multi_face_landmarks:
            result["instruction"] = "No face detected"
            return result
        
        # Face detected
        result["face_detected"] = True
        face_landmarks = results.multi_face_landmarks[0]
        
        # Get pose estimation
        x, y, z = self.get_pose_estimation(frame, face_landmarks)
        result["pose_angles"] = {"pitch": round(x, 2), "yaw": round(y, 2), "roll": round(z, 2)}
        
        # Get face bounding box (pixel coordinates)
        face_x, face_y, face_width, face_height = self.get_face_bounding_box(face_landmarks, img_w, img_h)
        self.face_width_history.append(face_width)
        if len(self.face_width_history) > 10:
            self.face_width_history.pop(0)
        
        # Convert bounding box to normalized coordinates (0-1)
        result["bounding_box"] = {
            "x": face_x / img_w,
            "y": face_y / img_h,
            "width": face_width / img_w,
            "height": face_height / img_h
        }
        
        # Extract normalized landmarks (468 points with x, y, z)
        result["landmarks"] = [
            {
                "x": lm.x,
                "y": lm.y,
                "z": lm.z
            }
            for lm in face_landmarks.landmark
        ]
        
        # Check if verification is completed
        if self.is_completed():
            result["instruction"] = "Verification completed!"
            return result
        
        # Process current step
        step_info = self.verification_steps[self.current_step]
        result["instruction"] = step_info["instruction"]
        
        # Check pose condition
        condition_met = step_info["condition"](x, y, z, step_info)
        result["condition_met"] = condition_met
        
        if condition_met:
            if self.step_start_time is None:
                self.step_start_time = time.time()
            
            elapsed = time.time() - self.step_start_time
            progress = min(elapsed / step_info["duration"], 1.0)
            result["progress"] = progress
            
            # NO DRAWING on frame - client will draw progress bar
            
            # Check if duration is met
            if elapsed >= step_info["duration"]:
                # Capture image
                face_crop, crop_info = self.crop_face_image(clean_image, face_landmarks, img_w, img_h)
                
                if face_crop is not None and face_crop.size > 0:
                    # Encode cropped face to JPEG
                    _, buffer = cv2.imencode('.jpg', face_crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
                    
                    capture_data = {
                        "step_name": step_info["name"],
                        "step_number": self.current_step + 1,
                        "instruction": step_info["instruction"],
                        "image_data": buffer.tobytes(),
                        "timestamp": datetime.utcnow().isoformat(),
                        "pose_angles": {
                            "pitch": round(x, 2),
                            "yaw": round(y, 2),
                            "roll": round(z, 2)
                        },
                        "face_width": face_width,
                        "crop_info": {
                            "x": crop_info[0],
                            "y": crop_info[1],
                            "width": crop_info[2],
                            "height": crop_info[3]
                        }
                    }
                    
                    self.captured_images_buffer.append(capture_data)
                    result["should_capture"] = True
                    result["capture_data"] = capture_data
                    
                    logger.info(f"Step {self.current_step + 1} captured: {step_info['name']}")
                
                # Move to next step (NO flash effect - client handles visual feedback)
                self.current_step += 1
                self.step_start_time = None
        else:
            self.step_start_time = None
        
        # NO UI DRAWING - all visual feedback handled by client
        # Client will draw: instruction, step counter, status, pose angles, progress bar
        
        return result
    
    def get_captured_images(self) -> List[Dict[str, Any]]:
        """Get all captured images from buffer."""
        return self.captured_images_buffer.copy()
    
    def clear_captured_images(self) -> None:
        """Clear captured images buffer."""
        self.captured_images_buffer.clear()
