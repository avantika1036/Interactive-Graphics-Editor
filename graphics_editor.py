import sys
import math
import json
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QColorDialog, QLineEdit, QOpenGLWidget, QStatusBar
)
from PyQt5.QtGui import QOpenGLContext, QColor, QCursor # Import QCursor
from PyQt5.QtCore import Qt, QSize

from OpenGL.GL import *
from OpenGL.GLU import *

# --- Configuration ---
INITIAL_WINDOW_WIDTH, INITIAL_WINDOW_HEIGHT = 1200, 700
MENU_WIDTH_PX = 200 # Fixed pixel width for the menu
MIN_CANVAS_WIDTH = 400 # Minimum width for the canvas area
MIN_WINDOW_HEIGHT = 600 # Minimum height for the entire window

DATA_FILE = "graphics_data.json"
GRID_SPACING = 20 # Grid spacing for snapping

# Global variables (will be managed by the main window/canvas class)
SCREEN_WIDTH = INITIAL_WINDOW_WIDTH
SCREEN_HEIGHT = INITIAL_WINDOW_HEIGHT
CANVAS_WIDTH = INITIAL_WINDOW_WIDTH - MENU_WIDTH_PX
MID_X = CANVAS_WIDTH // 2 # Midpoint of the canvas
MID_Y = SCREEN_HEIGHT // 2 # Midpoint of the canvas (vertical)


# --- Enum-like constants ---
# Drawing Algorithms
ALGO_DDA = 1
ALGO_BRESENHAM = 2
ALGO_SYMMETRICAL_DDA = 3
ALGO_MIDPOINT_CIRCLE = 4
ALGO_MIDPOINT_ELLIPSE = 5

# Line Styles
STYLE_SOLID = 1
STYLE_DOTTED = 2
STYLE_THICK = 3
STYLE_USER_DEFINED = 4

# Application Modes
MODE_IDLE = 0
MODE_DRAWING_LINE_P1 = 1
MODE_DRAWING_LINE_P2 = 2
MODE_DRAWING_CIRCLE_CENTER = 3
MODE_DRAWING_CIRCLE_RADIUS = 4
MODE_DRAWING_ELLIPSE_CENTER = 5
MODE_DRAWING_ELLIPSE_RX_POINT = 6
MODE_DRAWING_ELLIPSE_RY_POINT = 7

MODE_SELECTING_OBJECT = 8
MODE_APPLY_TRANSLATE = 9
MODE_APPLY_ROTATE = 10
MODE_APPLY_SCALE = 11
MODE_APPLY_REFLECT = 12 # This is now a general reflect mode
MODE_APPLY_REFLECT_LINE_P1 = 13 # New: First point for arbitrary line reflection
MODE_APPLY_REFLECT_LINE_P2 = 14 # New: Second point for arbitrary line reflection


# --- Colors ---
COLORS = {
    "BLACK": (0.0, 0.0, 0.0),
    "WHITE": (1.0, 1.0, 1.0),
    "RED": (1.0, 0.0, 0.0),
    "GREEN": (0.0, 1.0, 0.0),
    "BLUE": (0.0, 0.0, 1.0),
    "YELLOW": (1.0, 1.0, 0.0),
    "ORANGE": (1.0, 0.5, 0.0),
    "SELECTED_HIGHLIGHT": (1.0, 0.8, 0.2), # For highlighting selected object
    "CANVAS_BACKGROUND_LIGHT": (0.95, 0.95, 0.95), # Light grey for background
    "GRID_LINES_LIGHT": (0.7, 0.7, 0.7), # Darker grey for grid lines
    "AXIS_LINES_LIGHT": (0.4, 0.4, 0.4),  # Even darker grey for axis
    "TEMP_POINTS_LIGHT": (0.0, 0.0, 0.0), # Black for temp points on light background
    "REFLECTION_LINE": (0.8, 0.2, 0.8) # Magenta for the arbitrary reflection line
}

# --- Global State (Managed by MainWindow/OpenGLCanvas classes) ---
objects_to_draw = []
current_mode = MODE_IDLE
current_object_type = "line"
current_algo_func = None # References to drawing functions
current_style_choice = STYLE_SOLID
current_thickness = 1
current_mask = 0
current_color = COLORS["BLUE"] # Default starting color
temp_points = []
selected_object_id = -1 # Changed from None to -1
show_grid = True
next_object_id = 0

# --- Helper Functions (Independent of OpenGLCanvas class for now) ---
def logical_to_screen(lx, ly):
    # Convert logical coordinates (origin at canvas center) to screen coordinates (origin top-left of canvas's viewport)
    sx = lx + MID_X
    sy = MID_Y - ly
    return sx, sy

def screen_to_logical(sx, sy):
    # Convert screen coordinates (origin top-left of canvas's viewport) to logical coordinates (origin at canvas center)
    lx = sx - MID_X
    ly = MID_Y - sy # This correctly inverts the Y-axis from screen (top-down) to logical (bottom-up)
    return lx, ly # Return the calculated logical Y directly

def plot_styled_pixel(x_logical, y_logical, style, step, total_steps, mask):
    do_plot = False
    if style == STYLE_SOLID or style == STYLE_THICK:
        do_plot = True
    elif style == STYLE_DOTTED:
        if step % 4 < 2: # Simple on-off pattern
            do_plot = True
    elif style == STYLE_USER_DEFINED:
        if (mask >> (step % 16)) & 1:
            do_plot = True

    if do_plot:
        sx, sy = logical_to_screen(x_logical, y_logical)
        # Ensure pixel is drawn within the canvas area's local coordinates
        if 0 <= sx < CANVAS_WIDTH and 0 <= sy < SCREEN_HEIGHT:
            glBegin(GL_POINTS)
            glVertex2f(sx, sy)
            glEnd()

# --- Algorithms ---
# DDA Line Algorithm
def dda_line(x1, y1, x2, y2, style, thickness=1, mask=0):
    dx, dy = x2 - x1, y2 - y1
    steps = int(max(abs(dx), abs(dy)))
    if steps == 0:
        plot_styled_pixel(x1, y1, style, 0, 0, mask)
        return
    x_inc, y_inc = dx / steps, dy / steps
    x, y = float(x1), float(y1)
    for i in range(steps + 1):
        plot_styled_pixel(round(x), round(y), style, i, steps, mask)
        x += x_inc
        y += y_inc

# Symmetrical DDA Line Algorithm
def symmetrical_dda_line(x1, y1, x2, y2, style, thickness=1, mask=0):
    dx, dy = x2 - x1, y2 - y1
    steps = int(max(abs(dx), abs(dy)))
    if steps == 0:
        plot_styled_pixel(x1, y1, style, 0, 0, mask)
        return
    x_inc, y_inc = dx / steps, dy / steps
    
    x_mid, y_mid = float(x1), float(y1)
    for i in range(steps // 2 + 1):
        plot_styled_pixel(round(x_mid), round(y_mid), style, i, steps, mask)
        x_mid += x_inc
        y_mid += y_inc
    
    x_mid, y_mid = float(x2), float(y2)
    for i in range(steps - steps // 2):
        plot_styled_pixel(round(x_mid), round(y_mid), style, i + (steps // 2) + 1, steps, mask)
        x_mid -= x_inc
        y_mid -= y_inc

# Bresenham's Line Algorithm
def bresenham_line(x1, y1, x2, y2, style, thickness=1, mask=0):
    dx, dy = abs(x2 - x1), abs(y2 - y1)
    sx = 1 if x1 < x2 else -1
    sy = 1 if y1 < y2 else -1
    steep = dy > dx

    if steep:
        x1, y1 = y1, x1
        x2, y2 = y2, x2
        dx, dy = abs(x2 - x1), abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1

    dx = int(dx)
    dy = int(dy)

    p = 2 * dy - dx
    x, y = x1, y1

    for i in range(dx + 1):
        if steep:
            plot_styled_pixel(y, x, style, i, dx, mask)
        else:
            plot_styled_pixel(x, y, style, i, dx, mask)

        if p >= 0:
            y += sy
            p -= 2 * dx
        x += sx
        p += 2 * dy

# Midpoint Circle Algorithm
def draw_circle(x_c, y_c, r, style, thickness=1, mask=0):
    x, y = 0, r
    p = 1 - r
    i = 0
    while x <= y:
        # Plot 8 symmetrical points
        plot_styled_pixel(x_c + x, y_c + y, style, i, r, mask)
        plot_styled_pixel(x_c - x, y_c + y, style, i, r, mask)
        plot_styled_pixel(x_c + x, y_c - y, style, i, r, mask)
        plot_styled_pixel(x_c - x, y_c - y, style, i, r, mask)
        plot_styled_pixel(x_c + y, y_c + x, style, i, r, mask)
        plot_styled_pixel(x_c - y, y_c + x, style, i, r, mask)
        plot_styled_pixel(x_c + y, y_c - x, style, i, r, mask)
        plot_styled_pixel(x_c - y, y_c - x, style, i, r, mask)
        i += 1

        if p < 0:
            p += 2 * x + 3
        else:
            p += 2 * (x - y) + 5
            y -= 1
        x += 1

# Midpoint Ellipse Algorithm
def draw_ellipse(x_c, y_c, rx, ry, style, thickness=1, mask=0):
    # Region 1
    x, y = 0, ry
    p1 = ry * ry - rx * rx * ry + 0.25 * rx * rx
    i = 0
    while (2 * ry * ry * x) < (2 * rx * rx * y):
        plot_styled_pixel(x_c + x, y_c + y, style, i, max(rx, ry), mask)
        plot_styled_pixel(x_c - x, y_c + y, style, i, max(rx, ry), mask)
        plot_styled_pixel(x_c + x, y_c - y, style, i, max(rx, ry), mask)
        plot_styled_pixel(x_c - x, y_c - y, style, i, max(rx, ry), mask)
        i += 1

        if p1 < 0:
            x += 1
            p1 += 2 * ry * ry * x + ry * ry
        else:
            x += 1
            y -= 1
            p1 += 2 * ry * ry * x - 2 * rx * rx * y + ry * ry

    # Region 2
    p2 = ry * ry * (x + 0.5) * (x + 0.5) + rx * rx * (y - 1) * (y - 1) - rx * rx * ry * ry
    while y >= 0:
        plot_styled_pixel(x_c + x, y_c + y, style, i, max(rx, ry), mask)
        plot_styled_pixel(x_c - x, y_c + y, style, i, max(rx, ry), mask)
        plot_styled_pixel(x_c + x, y_c - y, style, i, max(rx, ry), mask)
        plot_styled_pixel(x_c - x, y_c - y, style, i, max(rx, ry), mask)
        i += 1

        if p2 > 0:
            y -= 1
            p2 -= 2 * rx * rx * y + rx * rx
        else:
            y -= 1
            x += 1
            p2 += 2 * ry * ry * x - 2 * rx * rx * y + rx * rx

# --- Style: thick object drawing ---
def draw_thick_object(effective_params, obj_type, thickness, mask, current_color_override):
    """
    Draws thick objects using their effective (transformed) parameters.
    """
    glLineWidth(thickness) # Set OpenGL line width for thick rendering

    if obj_type == "line":
        x1, y1, x2, y2 = effective_params["x1"], effective_params["y1"], effective_params["x2"], effective_params["y2"]
        
        # Calculate the vector for the line
        line_vec_x = x2 - x1
        line_vec_y = y2 - y1
        
        # Calculate the perpendicular vector
        perp_vec_x = -line_vec_y
        perp_vec_y = line_vec_x
        
        # Normalize the perpendicular vector
        length = math.sqrt(perp_vec_x**2 + perp_vec_y**2)
        if length == 0: # Handle zero-length lines (single point)
            norm_perp_x, norm_perp_y = 0, 0
        else:
            norm_perp_x = perp_vec_x / length
            norm_perp_y = perp_vec_y / length
        
        # Scale by half the thickness
        half_thickness = thickness / 2.0
        scaled_perp_x = norm_perp_x * half_thickness
        scaled_perp_y = norm_perp_y * half_thickness
        
        # Calculate the four vertices of the thick line (as a rectangle)
        # Point 1: (x1 - scaled_perp_x, y1 - scaled_perp_y)
        # Point 2: (x1 + scaled_perp_x, y1 + scaled_perp_y)
        # Point 3: (x2 + scaled_perp_x, y2 + scaled_perp_y)
        # Point 4: (x2 - scaled_perp_x, y2 - scaled_perp_y)
        
        # Convert logical coordinates of vertices to screen coordinates
        v1_sx, v1_sy = logical_to_screen(x1 - scaled_perp_x, y1 - scaled_perp_y)
        v2_sx, v2_sy = logical_to_screen(x1 + scaled_perp_x, y1 + scaled_perp_y)
        v3_sx, v3_sy = logical_to_screen(x2 + scaled_perp_x, y2 + scaled_perp_y)
        v4_sx, v4_sy = logical_to_screen(x2 - scaled_perp_x, y2 - scaled_perp_y)
        
        glColor3fv(current_color_override)
        glBegin(GL_QUADS) # Draw as a filled rectangle
        glVertex2f(v1_sx, v1_sy)
        glVertex2f(v2_sx, v2_sy)
        glVertex2f(v3_sx, v3_sy)
        glVertex2f(v4_sx, v4_sy)
        glEnd()
        
    elif obj_type == "circle":
        xc, yc, r = effective_params["xc"], effective_params["yc"], effective_params["r"]
        # Draw concentric circles to simulate thickness
        for i in range(thickness):
            offset_r = r + (i - (thickness - 1) / 2.0)
            if offset_r >= 1: # Ensure radius is positive
                draw_circle(xc, yc, int(offset_r), STYLE_SOLID, 1, mask)
    elif obj_type == "ellipse":
        xc, yc, rx, ry = effective_params["xc"], effective_params["yc"], effective_params["rx"], effective_params["ry"]
        # Draw concentric ellipses to simulate thickness
        for i in range(thickness):
            offset_rx = rx + (i - (thickness - 1) / 2.0)
            offset_ry = ry + (i - (thickness - 1) / 2.0)
            if offset_rx >= 1 and offset_ry >= 1: # Ensure radii are positive
                draw_ellipse(xc, yc, int(offset_rx), int(offset_ry), STYLE_SOLID, 1, mask)
    
    glLineWidth(1.0) # Reset line width to default after drawing thick object

# --- Helper for reflecting a single point across a line ---
def reflect_point_across_line(px, py, line_p1x, line_p1y, line_p2x, line_p2y):
    # If the line is a single point, reflection is undefined or the point itself
    if line_p1x == line_p2x and line_p1y == line_p2y:
        return px, py # Or handle as an error/no reflection

    # Case 1: Vertical line (slope is infinite)
    if line_p1x == line_p2x:
        # Reflection across x = line_p1x
        reflected_x = 2 * line_p1x - px
        reflected_y = py
        return reflected_x, reflected_y

    # Case 2: Horizontal line (slope is zero)
    if line_p1y == line_p2y:
        # Reflection across y = line_p1y
        reflected_x = px
        reflected_y = 2 * line_p1y - py
        return reflected_x, reflected_y

    # Case 3: General line (y = mx + c)
    # Calculate slope (m) and y-intercept (c) of the reflection line
    m = (line_p2y - line_p1y) / (line_p2x - line_p1x)
    c = line_p1y - m * line_p1x

    # Formula for reflection of (px, py) across y = mx + c
    # Let (x', y') be the reflected point
    
    # Calculate denominator common to both formulas
    denom = 1 + m*m

    # Calculate reflected coordinates
    reflected_x = (px * (1 - m*m) + 2 * m * py - 2 * m * c) / denom
    reflected_y = (py * (m*m - 1) + 2 * m * px + 2 * c) / denom

    return reflected_x, reflected_y


# --- Transformations ---
def apply_transformations(obj):
    transformed_params = obj["params"].copy()
    
    for t in obj["transformations"]:
        if t["type"] == "translate":
            dx, dy = t["dx"], t["dy"]
            if obj["type"] == "line":
                transformed_params["x1"] += dx
                transformed_params["y1"] += dy
                transformed_params["x2"] += dx
                transformed_params["y2"] += dy
            elif obj["type"] == "circle" or obj["type"] == "ellipse":
                transformed_params["xc"] += dx
                transformed_params["yc"] += dy
        
        elif t["type"] == "rotate":
            angle_rad = math.radians(t["angle"])
            cx, cy = t["cx"], t["cy"] # Center of rotation is stored with the transformation
            
            if obj["type"] == "line":
                px, py = transformed_params["x1"], transformed_params["y1"]
                translated_x, translated_y = px - cx, py - cy
                rotated_x = translated_x * math.cos(angle_rad) - translated_y * math.sin(angle_rad)
                rotated_y = translated_x * math.sin(angle_rad) + translated_y * math.cos(angle_rad)
                transformed_params["x1"], transformed_params["y1"] = rotated_x + cx, rotated_y + cy

                px, py = transformed_params["x2"], transformed_params["y2"]
                translated_x, translated_y = px - cx, py - cy
                rotated_x = translated_x * math.cos(angle_rad) - translated_y * math.sin(angle_rad)
                rotated_y = translated_x * math.sin(angle_rad) + translated_y * math.cos(angle_rad)
                transformed_params["x2"], transformed_params["y2"] = rotated_x + cx, rotated_y + cy
            
            elif obj["type"] in ["circle", "ellipse"]:
                cx_obj, cy_obj = transformed_params["xc"], transformed_params["yc"]
                translated_x, translated_y = cx_obj - cx, cy_obj - cy
                rotated_cx = translated_x * math.cos(angle_rad) - translated_y * math.sin(angle_rad)
                rotated_cy = translated_x * math.sin(angle_rad) + translated_y * math.cos(angle_rad)
                transformed_params["xc"], transformed_params["yc"] = rotated_cx + cx, rotated_cy + cy

        elif t["type"] == "scale":
            sx, sy = t["sx"], t["sy"]
            fx, fy = t["fx"], t["fy"] # Fixed point for scaling is stored with the transformation
            
            if obj["type"] == "line":
                px, py = transformed_params["x1"], transformed_params["y1"]
                translated_x, translated_y = px - fx, py - fy
                scaled_x, scaled_y = translated_x * sx, translated_y * sy
                transformed_params["x1"], transformed_params["y1"] = scaled_x + fx, scaled_y + fy

                px, py = transformed_params["x2"], transformed_params["y2"]
                translated_x, translated_y = px - fx, py - fy
                scaled_x, scaled_y = translated_x * sx, translated_y * sy
                transformed_params["x2"], transformed_params["y2"] = scaled_x + fx, scaled_y + fy
            
            elif obj["type"] == "circle":
                # Ensure radius scaling makes sense: only scale by sx (or sy if isotropic)
                # For simplicity, apply x scale factor
                transformed_params["r"] *= sx
            
            elif obj["type"] == "ellipse":
                transformed_params["rx"] *= sx
                transformed_params["ry"] *= sy

        elif t["type"] == "reflect": # For X, Y, Origin reflections
            axis = t["axis"]
            
            if obj["type"] == "line":
                if axis == "x":
                    transformed_params["y1"] = -transformed_params["y1"]
                    transformed_params["y2"] = -transformed_params["y2"]
                elif axis == "y":
                    transformed_params["x1"] = -transformed_params["x1"]
                    transformed_params["x2"] = -transformed_params["x2"]
                elif axis == "origin":
                    transformed_params["x1"] = -transformed_params["x1"]
                    transformed_params["y1"] = -transformed_params["y1"]
                    transformed_params["x2"] = -transformed_params["x2"]
                    transformed_params["y2"] = -transformed_params["y2"]
            
            elif obj["type"] == "circle" or obj["type"] == "ellipse":
                if axis == "x":
                    transformed_params["yc"] = -transformed_params["yc"]
                elif axis == "y":
                    transformed_params["xc"] = -transformed_params["xc"]
                elif axis == "origin":
                    transformed_params["xc"] = -transformed_params["xc"]
                    transformed_params["yc"] = -transformed_params["yc"]
        
        elif t["type"] == "reflect_line": # New: Reflection across an arbitrary line
            line_p1x, line_p1y = t["line_p1"]
            line_p2x, line_p2y = t["line_p2"]

            if obj["type"] == "line":
                px, py = transformed_params["x1"], transformed_params["y1"]
                rx1, ry1 = reflect_point_across_line(px, py, line_p1x, line_p1y, line_p2x, line_p2y)
                transformed_params["x1"], transformed_params["y1"] = rx1, ry1

                px, py = transformed_params["x2"], transformed_params["y2"]
                rx2, ry2 = reflect_point_across_line(px, py, line_p1x, line_p1y, line_p2x, line_p2y)
                transformed_params["x2"], transformed_params["y2"] = rx2, ry2
            
            elif obj["type"] == "circle" or obj["type"] == "ellipse":
                cx, cy = transformed_params["xc"], transformed_params["yc"]
                rcx, rcy = reflect_point_across_line(cx, cy, line_p1x, line_p1y, line_p2x, line_p2y)
                transformed_params["xc"], transformed_params["yc"] = rcx, rcy
            # Radii for circles/ellipses are magnitudes, they don't change with reflection.
            # Only their center point is reflected.

    return transformed_params

# --- File I/O ---
def load_objects_from_file():
    global objects_to_draw, next_object_id
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            objects_to_draw = []
            max_id = 0
            for obj_data in data:
                # Convert color list from JSON back to tuple for consistency
                if 'color' in obj_data and isinstance(obj_data['color'], list):
                    obj_data['color'] = tuple(obj_data['color'])

                algo_map = {
                    "dda_line": dda_line,
                    "bresenham_line": bresenham_line,
                    "symmetrical_dda_line": symmetrical_dda_line,
                    "draw_circle": draw_circle,
                    "draw_ellipse": draw_ellipse
                }
                obj_data["algo"] = algo_map.get(obj_data["algorithm"])
                if obj_data["algo"]:
                    obj_data["id"] = int(obj_data["id"])
                    objects_to_draw.append(obj_data)
                    if obj_data["id"] > max_id:
                        max_id = obj_data["id"]
            next_object_id = max_id + 1
    else:
        objects_to_draw = []
        next_object_id = 0

def save_objects_to_file():
    serializable_objects = []
    for obj in objects_to_draw:
        temp_obj = obj.copy()
        algo_name_map = {
            dda_line: "dda_line",
            bresenham_line: "bresenham_line",
            symmetrical_dda_line: "symmetrical_dda_line",
            draw_circle: "draw_circle",
            draw_ellipse: "draw_ellipse"
        }
        temp_obj["algorithm"] = algo_name_map.get(temp_obj["algo"])
        del temp_obj["algo"]
        
        # Convert color tuple to list for JSON serialization
        if 'color' in temp_obj and isinstance(temp_obj['color'], tuple):
            temp_obj['color'] = list(temp_obj['color'])

        serializable_objects.append(temp_obj)

    with open(DATA_FILE, 'w') as f:
        json.dump(serializable_objects, f, indent=4)

# --- QOpenGLWidget for Canvas ---
class OpenGLCanvas(QOpenGLWidget):
    def __init__(self, main_window_ref, parent=None): # Accept main_window_ref
        super().__init__(parent)
        self.main_window_ref = main_window_ref # Store reference to MainWindow
        self.setObjectName("OpenGLCanvas")
        
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

    def minimumSizeHint(self):
        return QSize(MIN_CANVAS_WIDTH, MIN_WINDOW_HEIGHT)

    def sizeHint(self):
        return QSize(CANVAS_WIDTH, SCREEN_HEIGHT)

    def initializeGL(self):
        # --- Changed for Light Mode ---
        glClearColor(*COLORS["CANVAS_BACKGROUND_LIGHT"], 1.0) # Light background
        # ---
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glPointSize(1.0)
        glLineWidth(1.0)

        self.update_canvas_dimensions()

    def resizeGL(self, width, height):
        self.update_canvas_dimensions(width, height)

        glViewport(0, 0, CANVAS_WIDTH, SCREEN_HEIGHT)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(0, CANVAS_WIDTH, SCREEN_HEIGHT, 0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def update_canvas_dimensions(self, width=None, height=None):
        global SCREEN_WIDTH, SCREEN_HEIGHT, CANVAS_WIDTH, MID_X, MID_Y
        
        if width is None:
            width = self.width()
        if height is None:
            height = self.height()

        CANVAS_WIDTH = max(MIN_CANVAS_WIDTH, width)
        SCREEN_HEIGHT = max(MIN_WINDOW_HEIGHT, height)
        
        MID_X = CANVAS_WIDTH // 2
        MID_Y = SCREEN_HEIGHT // 2


    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT)

        if show_grid:
            # --- Changed for Light Mode ---
            glColor3fv(COLORS["GRID_LINES_LIGHT"]) # Darker grey for grid
            # ---
            glBegin(GL_LINES)
            for i in range(0, CANVAS_WIDTH, GRID_SPACING):
                glVertex2f(i, 0)
                glVertex2f(i, SCREEN_HEIGHT)
            for i in range(0, SCREEN_HEIGHT, GRID_SPACING):
                glVertex2f(0, i)
                glVertex2f(CANVAS_WIDTH, i)
            glEnd()

        # --- Changed for Light Mode ---
        glColor3fv(COLORS["AXIS_LINES_LIGHT"]) # Darker grey for axes
        # ---
        glLineWidth(2.0) # Make axes slightly thicker
        glBegin(GL_LINES)
        glVertex2f(0, MID_Y)
        glVertex2f(CANVAS_WIDTH, MID_Y)
        glVertex2f(MID_X, 0)
        glVertex2f(MID_X, SCREEN_HEIGHT)
        glEnd()
        glLineWidth(1.0) # Reset line width to default for other drawings


        for obj in objects_to_draw:
            current_color_override = obj["color"]
            if obj["id"] == selected_object_id:
                current_color_override = COLORS["SELECTED_HIGHLIGHT"]

            glColor3fv(current_color_override)
            effective_params = apply_transformations(obj) # Get transformed parameters

            if obj["style"] == STYLE_THICK:
                # Pass effective_params to draw_thick_object for correct rendering
                draw_thick_object(effective_params, obj["type"], obj["thickness"], obj["mask"], current_color_override)
            else:
                if obj["type"] == "line":
                    obj["algo"](effective_params["x1"], effective_params["y1"],
                                effective_params["x2"], effective_params["y2"],
                                obj["style"], obj["thickness"], obj["mask"])
                elif obj["type"] == "circle":
                    obj["algo"](effective_params["xc"], effective_params["yc"],
                                effective_params["r"], obj["style"], obj["thickness"], obj["mask"])
                elif obj["type"] == "ellipse":
                    obj["algo"](effective_params["xc"], effective_params["yc"],
                                effective_params["rx"], effective_params["ry"],
                                obj["style"], obj["thickness"], obj["mask"])
        
        # --- Changed for Light Mode ---
        glColor3fv(COLORS["TEMP_POINTS_LIGHT"]) # Black for temporary points
        # ---
        glPointSize(5.0)
        glBegin(GL_POINTS)
        for p in temp_points: # p should always be a tuple (x, y)
            sx, sy = logical_to_screen(p[0], p[1])
            glVertex2f(sx, sy)
        glEnd()
        glPointSize(1.0)

        # Draw the arbitrary reflection line being defined
        if current_mode == MODE_APPLY_REFLECT_LINE_P2 and len(temp_points) == 1:
            glColor3fv(COLORS["REFLECTION_LINE"]) # Magenta line
            glLineWidth(2.0)
            glBegin(GL_LINES)
            sx1, sy1 = logical_to_screen(temp_points[0][0], temp_points[0][1])
            # Corrected: Get global mouse position and map to canvas local
            global_mouse_pos = QCursor.pos()
            local_mouse_pos = self.mapFromGlobal(global_mouse_pos)
            current_logical_x, current_logical_y = screen_to_logical(local_mouse_pos.x(), local_mouse_pos.y())
            sx2, sy2 = logical_to_screen(current_logical_x, current_logical_y)
            glVertex2f(sx1, sy1)
            glVertex2f(sx2, sy2)
            glEnd()
            glLineWidth(1.0)


    def mousePressEvent(self, event):
        global current_mode, temp_points, selected_object_id, next_object_id
        global current_algo_func, current_object_type, current_style_choice, current_thickness, current_mask, current_color, show_grid

        # Access input_dialog_active via the stored main_window_ref
        if self.main_window_ref.input_dialog_active:
            return

        if event.button() == Qt.LeftButton:
            x_raw_screen = event.pos().x()
            y_raw_screen = event.pos().y()
            
            # Snap raw screen coordinates to the nearest grid intersection
            snapped_x_screen = round(x_raw_screen / GRID_SPACING) * GRID_SPACING
            snapped_y_screen = round(y_raw_screen / GRID_SPACING) * GRID_SPACING

            # Convert snapped screen coordinates to logical coordinates
            logical_x, logical_y = screen_to_logical(snapped_x_screen, snapped_y_screen)


            if current_algo_func is None and current_mode not in [MODE_SELECTING_OBJECT, MODE_APPLY_TRANSLATE, MODE_APPLY_REFLECT_LINE_P1, MODE_APPLY_REFLECT_LINE_P2]: # Added new reflect modes
                self.main_window_ref.update_status("Please select an algorithm or action from the menu first.", "red")
                current_mode = MODE_IDLE
                return
            
            if current_mode == MODE_DRAWING_LINE_P1:
                temp_points.append((logical_x, logical_y))
                current_mode = MODE_DRAWING_LINE_P2
                self.main_window_ref.update_status(f"Line P1 (snapped): ({logical_x}, {logical_y}). Click P2.", "#333333") 
            elif current_mode == MODE_DRAWING_LINE_P2:
                temp_points.append((logical_x, logical_y))
                x1, y1 = temp_points[0]
                x2, y2 = temp_points[1]
                objects_to_draw.append({
                    "id": next_object_id,
                    "type": "line",
                    "algo": current_algo_func,
                    "algorithm": {
                        dda_line: "dda_line",
                        bresenham_line: "bresenham_line",
                        symmetrical_dda_line: "symmetrical_dda_line"
                    }.get(current_algo_func, "unknown_line_algo"),
                    "params": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                    "color": current_color,
                    "style": current_style_choice,
                    "thickness": current_thickness,
                    "mask": current_mask,
                    "transformations": []
                })
                self.main_window_ref.update_status(f"Line P2 (snapped): ({logical_x}, {logical_y}). Line drawn.", "green")
                next_object_id += 1
                save_objects_to_file()
                temp_points = []
                current_mode = MODE_IDLE
                # Deactivate style and algorithm buttons after drawing
                self.main_window_ref._highlight_active_algo_button(None)
                self.main_window_ref._highlight_active_style_button(None)


            elif current_mode == MODE_DRAWING_CIRCLE_CENTER:
                temp_points.append((logical_x, logical_y))
                current_mode = MODE_DRAWING_CIRCLE_RADIUS
                self.main_window_ref.update_status(f"Circle Center (snapped): ({logical_x}, {logical_y}). Click for radius.", "#333333") 
            elif current_mode == MODE_DRAWING_CIRCLE_RADIUS:
                temp_points.append((logical_x, logical_y))
                cx, cy = temp_points[0]
                # Radius point also snapped
                rx_point, ry_point = logical_x, logical_y
                r = int(math.sqrt((rx_point - cx)**2 + (ry_point - cy)**2))
                if r == 0: r = 1
                objects_to_draw.append({
                    "id": next_object_id,
                    "type": "circle",
                    "algo": current_algo_func,
                    "algorithm": "draw_circle",
                    "params": {"xc": cx, "yc": cy, "r": r},
                    "color": current_color,
                    "style": current_style_choice,
                    "thickness": current_thickness,
                    "mask": current_mask,
                    "transformations": []
                })
                self.main_window_ref.update_status(f"Circle drawn with Center ({cx},{cy}), Radius {r}.", "green")
                next_object_id += 1
                save_objects_to_file()
                temp_points = []
                current_mode = MODE_IDLE
                # Deactivate style and algorithm buttons after drawing
                self.main_window_ref._highlight_active_algo_button(None)
                self.main_window_ref._highlight_active_style_button(None)


            elif current_mode == MODE_DRAWING_ELLIPSE_CENTER:
                # First click for ellipse is the center, snap it
                temp_points.append((logical_x, logical_y))
                current_mode = MODE_DRAWING_ELLIPSE_RX_POINT
                self.main_window_ref.update_status(f"Ellipse Center (snapped): ({logical_x}, {logical_y}). Click for X-Radius point.", "#333333") 

            elif current_mode == MODE_DRAWING_ELLIPSE_RX_POINT:
                # Second click for ellipse defines X-Radius point
                # Store this point's coordinates in temp_points
                temp_points.append((logical_x, logical_y))
                current_mode = MODE_DRAWING_ELLIPSE_RY_POINT
                # Calculate rx here for feedback, but the actual calculation for the object
                # will happen in the next stage.
                cx, cy = temp_points[0]
                rx = abs(logical_x - cx)
                self.main_window_ref.update_status(f"Ellipse X-Radius point (snapped): ({logical_x},{logical_y}), current Rx {rx}. Click for Y-Radius point.", "#333333") 


            elif current_mode == MODE_DRAWING_ELLIPSE_RY_POINT:
                temp_points.append((logical_x, logical_y))
                cx, cy = temp_points[0]
                rx_point_x, rx_point_y = temp_points[1] # Retrieve the second clicked point
                ry_point_x, ry_point_y = logical_x, logical_y # This is the newly clicked point

                rx_val = abs(rx_point_x - cx) # Calculate Rx from center and RX point
                ry = abs(ry_point_y - cy)     # Calculate Ry from center and RY point

                if rx_val == 0: rx_val = 1
                if ry == 0: ry = 1

                objects_to_draw.append({
                    "id": next_object_id,
                    "type": "ellipse",
                    "algo": current_algo_func,
                    "algorithm": "draw_ellipse",
                    "params": {"xc": cx, "yc": cy, "rx": rx_val, "ry": ry},
                    "color": current_color,
                    "style": current_style_choice,
                    "thickness": current_thickness,
                    "mask": current_mask,
                    "transformations": []
                })
                self.main_window_ref.update_status(f"Ellipse drawn with Center ({cx},{cy}), Rx {rx_val}, Ry {ry}.", "green")
                next_object_id += 1
                save_objects_to_file()
                temp_points = []
                current_mode = MODE_IDLE
                # Deactivate style and algorithm buttons after drawing
                self.main_window_ref._highlight_active_algo_button(None)
                self.main_window_ref._highlight_active_style_button(None)

            elif current_mode == MODE_SELECTING_OBJECT:
                selected_object_id = -1
                min_effective_distance = float('inf') # This will be the distance used to find the truly closest object boundary
                closest_obj_id = -1
                
                # Base pixel tolerance for selection, independent of object thickness
                base_selection_pixel_tolerance = 10 

                self.main_window_ref.update_status(f"Click (logical): ({logical_x}, {logical_y})", "#333333")

                for obj in objects_to_draw:
                    effective_params = apply_transformations(obj)
                    current_obj_thickness = obj.get("thickness", 1)
                    
                    # This is how much the object's visual edge is effectively extended outwards from its nominal boundary.
                    # For a thickness of 1, this is 0. For 3, it's 1 (1.5 - 0.5). For even thickness (e.g., 2), it's 0.5.
                    # For a thickness of 1, half_nominal_thickness is 0.
                    half_nominal_thickness = (current_obj_thickness - 1) / 2.0 

                    current_obj_hit_distance = float('inf') # Distance from click to this object's visual extent

                    if obj["type"] == "line":
                        p1 = (effective_params["x1"], effective_params["y1"])
                        p2 = (effective_params["x2"], effective_params["y2"])
                        
                        line_dx, line_dy = p2[0] - p1[0], p2[1] - p1[1]
                        point_dx, point_dy = logical_x - p1[0], logical_y - p1[1]
                        
                        dot_product = point_dx * line_dx + point_dy * line_dy
                        length_sq = line_dx**2 + line_dy**2
                        
                        dist_to_line_segment_center = float('inf')
                        if length_sq == 0: # Handle single point lines
                            dist_to_line_segment_center = math.sqrt(point_dx**2 + point_dy**2)
                        else:
                            t = max(0.0, min(1.0, dot_product / length_sq))
                            closest_x_on_segment = p1[0] + t * line_dx
                            closest_y_on_segment = p1[1] + t * line_dy
                            dist_to_line_segment_center = math.sqrt((logical_x - closest_x_on_segment)**2 + (logical_y - closest_y_on_segment)**2)
                        
                        # A line is considered hit if the click is within its visual thickness + base_selection_pixel_tolerance
                        if dist_to_line_segment_center <= half_nominal_thickness + base_selection_pixel_tolerance:
                            # For sorting, use the distance to the effective outer edge of the thick line
                            current_obj_hit_distance = abs(dist_to_line_segment_center - half_nominal_thickness)
                            
                    elif obj["type"] == "circle":
                        center_x, center_y = effective_params["xc"], effective_params["yc"]
                        base_radius = effective_params["r"]
                        
                        dist_to_center = math.sqrt((logical_x - center_x)**2 + (logical_y - center_y)**2)
                        
                        # Effective outer radius including its own thickness
                        outer_radius_visual = base_radius + half_nominal_thickness

                        if dist_to_center <= outer_radius_visual + base_selection_pixel_tolerance:
                            # If it's a hit, the sorting distance is how close it is to the outer visual boundary
                            current_obj_hit_distance = abs(dist_to_center - outer_radius_visual)

                    elif obj["type"] == "ellipse":
                        center_x, center_y = effective_params["xc"], effective_params["yc"]
                        base_rx = effective_params["rx"]
                        base_ry = effective_params["ry"]

                        # Effective outer radii including its own thickness
                        outer_rx_visual = base_rx + half_nominal_thickness
                        outer_ry_visual = base_ry + half_nominal_thickness

                        if outer_rx_visual > 0 and outer_ry_visual > 0:
                            # Normalize the click point relative to the ellipse's center and visual radii
                            # Also consider the base_selection_pixel_tolerance in the normalization for hit detection
                            normalized_x = (logical_x - center_x) / (outer_rx_visual + base_selection_pixel_tolerance)
                            normalized_y = (logical_y - center_y) / (outer_ry_visual + base_selection_pixel_tolerance) # Corrected typo ry_visual
                            
                            ellipse_value_for_hitbox = (normalized_x**2) + (normalized_y**2)

                            if ellipse_value_for_hitbox <= 1.0: # If inside this generous hitbox
                                # For sorting, project the point to the outer visual ellipse and calculate distance
                                # This is still an approximation for sorting, but better than arbitrary small values.
                                # A simple approach: use distance to center, scaled inversely by radius, for sorting
                                current_obj_hit_distance = math.sqrt((logical_x - center_x)**2 + (logical_y - center_y)**2) / max(1.0, outer_rx_visual, outer_ry_visual)
                            else:
                                current_obj_hit_distance = float('inf') # Not a hit
                        else: # Fallback for degenerate ellipses (zero radii)
                            dist_to_center = math.sqrt((logical_x - center_x)**2 + (logical_y - center_y)**2)
                            if dist_to_center <= base_selection_pixel_tolerance:
                                current_obj_hit_distance = 0
                            else:
                                current_obj_hit_distance = float('inf')

                    if current_obj_hit_distance < min_effective_distance:
                        min_effective_distance = current_obj_hit_distance
                        closest_obj_id = obj["id"]
                
                if closest_obj_id != -1: # Use -1 for "no object"
                    selected_object_id = closest_obj_id
                    self.main_window_ref.update_status(f"Object {selected_object_id} selected. Closest effective distance: {min_effective_distance:.2f}", "blue")
                else:
                    selected_object_id = -1
                    self.main_window_ref.update_status("No object selected.", "red")
                current_mode = MODE_IDLE # Reset to idle after selection attempt
                self.main_window_ref._highlight_active_transform_button(None) # Clear transform buttons
                self.main_window_ref._highlight_active_object_action_button(None) # Clear object action buttons
                self.main_window_ref._highlight_active_algo_button(None) # Also clear algorithm highlight
                self.main_window_ref._highlight_active_style_button(None) # Also clear style highlight


            elif selected_object_id != -1 and current_mode == MODE_APPLY_TRANSLATE:
                obj_to_transform = next((obj for obj in objects_to_draw if obj["id"] == selected_object_id), None)
                if obj_to_transform:
                    if not temp_points:
                        temp_points.append((logical_x, logical_y))
                        self.main_window_ref.update_status(f"Translation start point (snapped): ({logical_x}, {logical_y}). Click destination.", "#333333") 
                    else:
                        start_x, start_y = temp_points[0]
                        dx, dy = logical_x - start_x, logical_y - start_y
                        obj_to_transform["transformations"].append({"type": "translate", "dx": dx, "dy": dy})
                        self.main_window_ref.update_status(f"Translated by ({dx}, {dy}).", "blue")
                        save_objects_to_file()
                        temp_points = []
                        selected_object_id = -1 # Deselect after transformation
                        current_mode = MODE_IDLE # Reset mode
                        self.main_window_ref._highlight_active_transform_button(None) # Clear transform buttons
                        self.main_window_ref._highlight_active_algo_button(None) # Also clear algorithm highlight
                        self.main_window_ref._highlight_active_style_button(None) # Also clear style highlight
                else:
                    self.main_window_ref.update_status("No object selected for translation.", "red")
                    selected_object_id = -1 # Ensure deselected if somehow lost
                    current_mode = MODE_IDLE # Reset mode
                    self.main_window_ref._highlight_active_transform_button(None) # Clear transform buttons
                    self.main_window_ref._highlight_active_algo_button(None) # Also clear algorithm highlight
                    self.main_window_ref._highlight_active_style_button(None) # Also clear style highlight
            
            # --- New: Handling arbitrary line reflection clicks ---
            elif selected_object_id != -1 and current_mode == MODE_APPLY_REFLECT_LINE_P1:
                temp_points.append((logical_x, logical_y))
                current_mode = MODE_APPLY_REFLECT_LINE_P2
                self.main_window_ref.update_status(f"Line Reflection P1 (snapped): ({logical_x}, {logical_y}). Click P2 to define reflection line.", "#333333")
            elif selected_object_id != -1 and current_mode == MODE_APPLY_REFLECT_LINE_P2:
                obj_to_transform = next((obj for obj in objects_to_draw if obj["id"] == selected_object_id), None)
                if obj_to_transform:
                    temp_points.append((logical_x, logical_y))
                    line_p1x, line_p1y = temp_points[0]
                    line_p2x, line_p2y = temp_points[1]
                    
                    obj_to_transform["transformations"].append({
                        "type": "reflect_line",
                        "line_p1": (line_p1x, line_p1y),
                        "line_p2": (line_p2x, line_p2y)
                    })
                    self.main_window_ref.update_status(f"Reflected across line from ({line_p1x}, {line_p1y}) to ({line_p2x}, {line_p2y}).", "blue")
                    save_objects_to_file()
                    temp_points = []
                    selected_object_id = -1 # Deselect after transformation
                    current_mode = MODE_IDLE
                    self.main_window_ref._highlight_active_transform_button(None) # Clear transform buttons
                    self.main_window_ref._highlight_active_algo_button(None) # Also clear algorithm highlight
                    self.main_window_ref._highlight_active_style_button(None) # Also clear style highlight
                else:
                    self.main_window_ref.update_status("No object selected for line reflection.", "red")
                    selected_object_id = -1
                    current_mode = MODE_IDLE
                    self.main_window_ref._highlight_active_transform_button(None) # Clear transform buttons
                    self.main_window_ref._highlight_active_algo_button(None) # Also clear algorithm highlight
                    self.main_window_ref._highlight_active_style_button(None) # Also clear style highlight
            # --- End new reflection handling ---

        self.update()
    
    def mouseMoveEvent(self, event):
        # Update canvas for dynamic line drawing feedback during arbitrary line reflection
        if current_mode == MODE_APPLY_REFLECT_LINE_P2 and len(temp_points) == 1:
            self.update() # Request a repaint to show the temporary reflection line


    def keyPressEvent(self, event):
        # Pass key events to the main window's input dialog handler if active
        if self.main_window_ref.input_dialog_active:
            pass # Let QLineEdit handle it
        elif event.key() == Qt.Key_Escape:
            save_objects_to_file()
            QApplication.instance().quit()


# --- Main Application Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt5 OpenGL Interactive Graphics Project")
        self.setGeometry(100, 100, INITIAL_WINDOW_WIDTH, INITIAL_WINDOW_HEIGHT)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        menu_widget = QWidget()
        menu_widget.setFixedWidth(MENU_WIDTH_PX)
        menu_widget.setStyleSheet("background-color: #E6E6E6;") # Lighter grey for menu background
        menu_layout = QVBoxLayout(menu_widget)
        menu_layout.setAlignment(Qt.AlignTop)
        
        self.opengl_canvas = OpenGLCanvas(self)
        main_layout.addWidget(menu_widget)
        main_layout.addWidget(self.opengl_canvas)

        # --- UI State for highlighting active buttons ---
        self.active_algo_button = None
        self.active_style_button = None
        self.active_transform_button = None # New: for active transform button
        self.active_object_action_button = None # New: for active object action button
        # --- Initialize button attributes BEFORE they are referenced in _add_button calls ---
        self.translate_btn = None
        self.rotate_btn = None
        self.scale_btn = None
        self.reflect_btn = None
        self.select_obj_btn = None
        # ---

        # Define color palettes for each group
        self.color_palettes = {
            "view": ("#6A8EAE", "#557A95", "#7C9CBF", "#4D6B82"), # Soft blue
            "transformations": ("#4A6B8A", "#3B5A75", "#5C7DA3", "#30495E"), # Professional blue-grey
            "object_actions": ("#707070", "#555555", "#808080", "#404040"), # Neutral grey
            "color": ("#6B9D7E", "#5A8B6A", "#7CAE8F", "#4F7C5B"), # Inviting green
            "style": ("#A0A0A0", "#8C8C8C", "#B0B0B0", "#7D7D7D"), # Light grey (for toggle-like)
            "algorithm": ("#457B9D", "#3B6A80", "#5A8BB0", "#305A6B"), # Deep blue
            "active_green": ("#8BC34A", "#689F38", "#AED581", "#7CB342") # Green for active state
        }

        self._add_menu_section(menu_layout, "VIEW")
        self._add_button(menu_layout, "Toggle Grid", self.toggle_grid, group_key="view")

        self._add_menu_section(menu_layout, "TRANSFORMATIONS")
        # Modified to pass button reference
        self.translate_btn = self._add_button(menu_layout, "Translate", lambda btn=self.translate_btn: self.set_mode(MODE_APPLY_TRANSLATE, "Translate", btn), group_key="transformations")
        self.rotate_btn = self._add_button(menu_layout, "Rotate", lambda btn=self.rotate_btn: self.prompt_rotate(btn), group_key="transformations") # Pass button to prompt_rotate
        self.scale_btn = self._add_button(menu_layout, "Scale", lambda btn=self.scale_btn: self.prompt_scale(btn), group_key="transformations") # Pass button to prompt_scale
        self.reflect_btn = self._add_button(menu_layout, "Reflect", lambda btn=self.reflect_btn: self.prompt_reflect(btn), group_key="transformations") # Pass button to prompt_reflect


        self._add_menu_section(menu_layout, "OBJECT ACTIONS")
        # Modified to pass button reference
        self.select_obj_btn = self._add_button(menu_layout, "Select Object", lambda btn=self.select_obj_btn: self.set_mode(MODE_SELECTING_OBJECT, "Select Object", btn), group_key="object_actions")
        self._add_button(menu_layout, "Edit Selected", self.prompt_edit_object, group_key="object_actions")
        self._add_button(menu_layout, "Delete Selected", self.delete_selected_object, group_key="object_actions")

        self._add_menu_section(menu_layout, "COLOR")
        self._add_button(menu_layout, "Pick Color", self.pick_color_dialog, group_key="color")
        self.color_swatch = QLabel()
        self.color_swatch.setFixedSize(60, 20)
        self.color_swatch.setStyleSheet(f"background-color: rgb({int(current_color[0]*255)}, {int(current_color[1]*255)}, {int(current_color[2]*255)}); border: 1px solid #555555; border-radius: 5px;") # Darker border for light mode swatch
        menu_layout.addWidget(self.color_swatch)


        self._add_menu_section(menu_layout, "STYLE (for next obj)")
        style_layout_row1 = QHBoxLayout()
        self.solid_btn = self._add_style_button(style_layout_row1, "Solid", STYLE_SOLID, group_key="style")
        self.dotted_btn = self._add_style_button(style_layout_row1, "Dotted", STYLE_DOTTED, group_key="style")
        menu_layout.addLayout(style_layout_row1)

        style_layout_row2 = QHBoxLayout()
        self.thick_btn = self._add_style_button(style_layout_row2, "Thick", STYLE_THICK, group_key="style")
        self.user_def_btn = self._add_style_button(style_layout_row2, "User-Def", STYLE_USER_DEFINED, group_key="style")
        menu_layout.addLayout(style_layout_row2)

        self.thickness_label = QLabel(f"Thickness: {current_thickness}")
        self.thickness_label.setStyleSheet("color: #333333; margin-top: 2px; margin-bottom: 2px;") # Darker text for light mode, reduced margin
        menu_layout.addWidget(self.thickness_label)
        self.mask_label = QLabel(f"Mask: 0x{current_mask:04X}")
        self.mask_label.setStyleSheet("color: #333333; margin-top: 2px; margin-bottom: 2px;") # Darker text for light mode, reduced margin
        menu_layout.addWidget(self.mask_label)

        self._add_menu_section(menu_layout, "ALGORITHM (for next obj)")
        self.dda_line_btn = self._add_algo_button(menu_layout, "Simple DDA Line", ALGO_DDA, "line", click_mode=MODE_DRAWING_LINE_P1, group_key="algorithm")
        self.bresenham_btn = self._add_algo_button(menu_layout, "Bresenham Line", ALGO_BRESENHAM, "line", click_mode=MODE_DRAWING_LINE_P1, group_key="algorithm")
        self.symm_dda_btn = self._add_algo_button(menu_layout, "Symmetrical DDA", ALGO_SYMMETRICAL_DDA, "line", click_mode=MODE_DRAWING_LINE_P1, group_key="algorithm")
        self.midpt_circle_btn = self._add_algo_button(menu_layout, "Midpoint Circle", ALGO_MIDPOINT_CIRCLE, "circle", click_mode=MODE_DRAWING_CIRCLE_CENTER, group_key="algorithm")
        self.midpt_ellipse_btn = self._add_algo_button(menu_layout, "Midpoint Ellipse", ALGO_MIDPOINT_ELLIPSE, "ellipse", click_mode=MODE_DRAWING_ELLIPSE_CENTER, group_key="algorithm")
        
        self.input_dialog_active = False
        self.input_dialog_prompt = ""
        self.input_dialog_callback = None
        self.input_dialog_widget = QLineEdit(self)
        self.input_dialog_widget.hide()
        self.input_dialog_widget.returnPressed.connect(self.handle_input_dialog_return_pressed)
        self.input_dialog_widget.textChanged.connect(self.handle_input_dialog_text_changed)
        self.input_dialog_widget.installEventFilter(self)
        self.input_dialog_widget.setStyleSheet("""
            QLineEdit {
                background-color: #F8F8F8; /* Very light grey */
                color: #333333; /* Dark text */
                border: 1px solid #CCCCCC; /* Light grey border */
                border-radius: 5px;
                padding: 5px;
            }
        """)

        # --- Status Bar ---
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.update_status("Welcome! Select an algorithm to begin drawing.", "black")
        # ---

        load_objects_from_file()
        self.update_color_swatch()


    def _add_menu_section(self, layout, title):
        label = QLabel(title)
        label.setStyleSheet("font-weight: bold; margin-top: 5px; margin-bottom: 2px; color: #333333;")
        layout.addWidget(label)

    def _add_button(self, layout, text, callback, group_key="dark_grey"): # Added group_key
        btn = QPushButton(text)
        # Use a lambda that captures the `btn` when defining the callback for proper highlighting
        if "Translate" in text or "Select Object" in text: # These set mode directly
            btn.clicked.connect(lambda checked=False, b=btn: callback(b))
        elif "Rotate" in text or "Scale" in text or "Reflect" in text: # These prompt, then set mode
            btn.clicked.connect(lambda checked=False, b=btn: callback(b))
        else: # Other buttons like "Toggle Grid", "Edit Selected", "Delete Selected", "Pick Color"
            btn.clicked.connect(callback)


        btn.setFixedWidth(MENU_WIDTH_PX - 20) # Explicitly set fixed width, accounting for margins/padding

        c1, c2, h1, h2 = self.color_palettes.get(group_key, self.color_palettes["object_actions"]) # Default to object_actions grey
        active_c1, active_c2, active_h1, active_h2 = self.color_palettes["active_green"] # Use green for active

        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c1}, stop:1 {c2});
                color: white;
                border: none;
                padding: 6px 10px;
                text-align: center;
                text-decoration: none;
                font-size: 14px;
                margin: 2px 2px;
                border-radius: 8px;
                box-shadow: 2px 2px 5px rgba(0, 0, 0, 0.2);
            }}
            QPushButton:hover {{
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {h1}, stop:1 {h2});
                box-shadow: 2px 2px 7px rgba(0, 0, 0, 0.3);
            }}
            QPushButton:pressed {{
                background-color: {h2};
                box-shadow: inset 1px 1px 3px rgba(0, 0, 0, 0.4);
            }}
            QPushButton.active {{ /* Style for active state */
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #28a745, stop:1 #218838);
                color: white;
                font-weight: bold;
                box-shadow: 2px 2px 5px rgba(0, 0, 0, 0.3);
            }}
        """)
        layout.addWidget(btn)
        return btn

    def _add_style_button(self, layout, text, style_enum, group_key="style"): # Added group_key
        btn = QPushButton(text)
        btn.clicked.connect(lambda: self.set_style(style_enum, btn))
        btn.setFixedWidth(int((MENU_WIDTH_PX - 20) / 2 - 4)) # Adjusted fixed width for two buttons in a row

        c1, c2, h1, h2 = self.color_palettes.get(group_key, self.color_palettes["style"])
        active_c1, active_c2, active_h1, active_h2 = self.color_palettes["active_green"] # Use green for active

        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c1}; /* Solid color for inactive styles */
                color: #333333;
                border: none;
                padding: 4px 8px;
                text-align: center;
                text-decoration: none;
                font-size: 12px;
                margin: 2px 2px;
                border-radius: 6px;
                box-shadow: 1px 1px 3px rgba(0, 0, 0, 0.1);
            }}
            QPushButton:hover {{
                background-color: {h1};
                box-shadow: 1px 1px 5px rgba(0, 0, 0, 0.2);
            }}
            QPushButton.active {{
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #28a745, stop:1 #218838);
                color: white;
                font-weight: bold;
                box-shadow: 2px 2px 5px rgba(0, 0, 0, 0.3);
            }}
        """)
        layout.addWidget(btn)
        return btn

    def _add_algo_button(self, layout, text, algo_enum, obj_type, click_mode, group_key="algorithm"): # Added group_key
        btn = QPushButton(text)
        algo_func = {
            ALGO_DDA: dda_line,
            ALGO_BRESENHAM: bresenham_line,
            ALGO_SYMMETRICAL_DDA: symmetrical_dda_line,
            ALGO_MIDPOINT_CIRCLE: draw_circle,
            ALGO_MIDPOINT_ELLIPSE: draw_ellipse
        }[algo_enum]
        btn.clicked.connect(lambda: self.set_algorithm(algo_func, obj_type, click_mode, btn))
        btn.setFixedWidth(MENU_WIDTH_PX - 20) # Explicitly set fixed width

        c1, c2, h1, h2 = self.color_palettes.get(group_key, self.color_palettes["algorithm"])
        active_c1, active_c2, active_h1, active_h2 = self.color_palettes["active_green"] # Use green for active

        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c1}, stop:1 {c2});
                color: white;
                border: none;
                padding: 6px 10px;
                text-align: center;
                text-decoration: none;
                font-size: 14px;
                margin: 2px 2px;
                border-radius: 8px;
                box-shadow: 2px 2px 5px rgba(0, 0, 0, 0.2);
            }}
            QPushButton:hover {{
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {h1}, stop:1 {h2});
                box-shadow: 2px 2px 7px rgba(0, 0, 0, 0.3);
            }}
            QPushButton:pressed {{
                background-color: {h2};
                box-shadow: inset 1px 1px 3px rgba(0, 0, 0, 0.4);
            }}
            QPushButton.active {{
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #28a745, stop:1 #218838);
                color: white;
                font-weight: bold;
                box-shadow: 2px 2px 5px rgba(0, 0, 0, 0.3);
            }}
        """)
        layout.addWidget(btn)
        return btn

    def _highlight_active_algo_button(self, new_active_button):
        if self.active_algo_button:
            # Remove 'active' class from old button
            self.active_algo_button.setProperty("class", "")
            self.active_algo_button.setStyleSheet(self.active_algo_button.styleSheet())
        
        if new_active_button:
            # Add 'active' class to new button
            new_active_button.setProperty("class", "active")
            new_active_button.setStyleSheet(new_active_button.styleSheet())
        self.active_algo_button = new_active_button
    
    def _highlight_active_style_button(self, new_active_button):
        if self.active_style_button:
            self.active_style_button.setProperty("class", "")
            self.active_style_button.setStyleSheet(self.active_style_button.styleSheet())
        
        if new_active_button:
            new_active_button.setProperty("class", "active")
            new_active_button.setStyleSheet(new_active_button.styleSheet())
        self.active_style_button = new_active_button
    
    # New: Highlight active transformation button
    def _highlight_active_transform_button(self, new_active_button):
        if self.active_transform_button:
            self.active_transform_button.setProperty("class", "")
            self.active_transform_button.setStyleSheet(self.active_transform_button.styleSheet())
        
        if new_active_button:
            new_active_button.setProperty("class", "active")
            new_active_button.setStyleSheet(new_active_button.styleSheet())
        self.active_transform_button = new_active_button

    # New: Highlight active object action button
    def _highlight_active_object_action_button(self, new_active_button):
        if self.active_object_action_button:
            self.active_object_action_button.setProperty("class", "")
            self.active_object_action_button.setStyleSheet(self.active_object_action_button.styleSheet())
        
        if new_active_button:
            new_active_button.setProperty("class", "active")
            new_active_button.setStyleSheet(new_active_button.styleSheet())
        self.active_object_action_button = new_active_button


    def update_status(self, message, color="black"): # Default status color to black for light mode
        self.statusBar.setStyleSheet(f"QStatusBar {{ color: {color}; }}")
        self.statusBar.showMessage(message)

    def update_color_swatch(self):
        r, g, b = int(current_color[0]*255), int(current_color[1]*255), int(current_color[2]*255)
        self.color_swatch.setStyleSheet(f"background-color: rgb({r}, {g}, {b}); border: 1px solid #555555; border-radius: 5px;")


    def set_mode(self, mode, description="", button_ref=None): # Added button_ref
        global current_mode, temp_points, selected_object_id
        
        # Clear previous active states when entering a new mode
        if current_mode not in [MODE_DRAWING_LINE_P1, MODE_DRAWING_LINE_P2, MODE_DRAWING_CIRCLE_CENTER, MODE_DRAWING_CIRCLE_RADIUS, MODE_DRAWING_ELLIPSE_CENTER, MODE_DRAWING_ELLIPSE_RX_POINT, MODE_DRAWING_ELLIPSE_RY_POINT]:
            self._highlight_active_algo_button(None) # Clear algorithm button highlight
        self._highlight_active_style_button(None) # Clear style button highlight
        self._highlight_active_transform_button(None) # Clear transform button highlight
        self._highlight_active_object_action_button(None) # Clear object action button highlight

        current_mode = mode
        temp_points = []
        # Keep selected object for transformations, but clear for drawing or new selections
        if mode in [MODE_DRAWING_LINE_P1, MODE_DRAWING_CIRCLE_CENTER, MODE_DRAWING_ELLIPSE_CENTER, MODE_IDLE, MODE_SELECTING_OBJECT]:
             selected_object_id = -1
        
        # Apply new active state if a button reference is provided and it's a transform/object action
        if button_ref:
            if mode in [MODE_APPLY_TRANSLATE, MODE_APPLY_ROTATE, MODE_APPLY_SCALE, MODE_APPLY_REFLECT, MODE_APPLY_REFLECT_LINE_P1]:
                self._highlight_active_transform_button(button_ref)
            elif mode == MODE_SELECTING_OBJECT:
                self._highlight_active_object_action_button(button_ref)


        self.update_status(f"Mode changed to: {description}", "black")
        self.opengl_canvas.update()

    def toggle_grid(self):
        global show_grid
        show_grid = not show_grid
        self.update_status(f"Grid toggled {'ON' if show_grid else 'OFF'}", "black")
        self.opengl_canvas.update()

    def set_color(self, color_val):
        global current_color
        current_color = color_val
        r, g, b = int(color_val[0]*255), int(color_val[1]*255), int(color_val[2]*255)
        self.update_status(f"Set current color to: #{r:02X}{g:02X}{b:02X}", "black")
        self.update_color_swatch()
        self.opengl_canvas.update()

    def set_style(self, style_enum, button_ref=None):
        global current_style_choice, current_thickness, current_mask
        current_style_choice = style_enum
        self.update_status(f"Selected style: {style_enum}", "black")
        
        self._highlight_active_style_button(button_ref) # Highlight the clicked style button
        # self._highlight_active_algo_button(None) # Clear algo
        self._highlight_active_transform_button(None) # Clear transform
        self._highlight_active_object_action_button(None) # Clear object action


        if current_style_choice == STYLE_THICK:
            self.activate_input_dialog("Enter thickness (integer):", self._thickness_input_callback)
        elif current_style_choice == STYLE_USER_DEFINED:
            self.activate_input_dialog("Enter hex mask (e.g., F0F0):", self._mask_input_callback)
        self.opengl_canvas.update()

    def _thickness_input_callback(self, value_str):
        global current_thickness
        try:
            thickness_input = int(value_str)
            if thickness_input > 0: current_thickness = thickness_input
            else: self.update_status("Thickness must be positive. Using default 1.", "red")
        except ValueError:
            self.update_status("Invalid thickness. Using default 1.", "red")
            current_thickness = 1
        self.thickness_label.setText(f"Thickness: {current_thickness}")
        self.opengl_canvas.update()

    def _mask_input_callback(self, value_str):
        global current_mask
        try:
            current_mask = int(value_str, 16)
        except ValueError:
            self.update_status("Invalid mask. Using default 0x0000.", "red")
            current_mask = 0
        self.mask_label.setText(f"Mask: 0x{current_mask:04X}")
        self.opengl_canvas.update()

    def set_algorithm(self, algo_func, obj_type, click_mode, button_ref=None):
        global current_algo_func, current_object_type, current_mode, temp_points
        current_algo_func = algo_func
        current_object_type = obj_type
        temp_points = []
        selected_object_id = -1 # Deselect when starting new drawing
        current_mode = click_mode
        self.update_status(f"Selected algorithm: {algo_func.__name__}. Mode: {click_mode}. Click on canvas to draw.", "black")
        
        self._highlight_active_algo_button(button_ref) # Highlight the clicked algo button
        self._highlight_active_style_button(None) # Clear style
        self._highlight_active_transform_button(None) # Clear transform
        self._highlight_active_object_action_button(None) # Clear object action

        self.opengl_canvas.update()

    def pick_color_dialog(self):
        global current_color
        initial_qcolor = QColor(int(current_color[0]*255), int(current_color[1]*255), int(current_color[2]*255))
        color = QColorDialog.getColor(initial_qcolor, self, "Pick a Color")

        if color.isValid():
            r, g, b, _ = color.getRgbF()
            self.set_color((r, g, b))
    
    def prompt_edit_object(self):
        global selected_object_id
        if selected_object_id == -1: # Changed from None
            self.update_status("No object selected to edit.", "red")
            return

        obj_to_edit = next((obj for obj in objects_to_draw if obj["id"] == selected_object_id), None)
        if not obj_to_edit:
            self.update_status("Error: Selected object not found for editing.", "red")
            selected_object_id = -1 # Changed from None
            self.opengl_canvas.update()
            return

        # --- Bake transformations into base parameters before editing ---
        current_effective_params = apply_transformations(obj_to_edit)
        obj_to_edit["params"] = current_effective_params # Replace base params with current effective state
        obj_to_edit["transformations"] = [] # Clear existing transformations as they are now "baked"
        self.update_status(f"Baked transformations for object {selected_object_id}. You can now edit its base parameters or apply new transforms.", "#333333")
        # --- END NEW ---

        # Define nested callback functions BEFORE they are used
        def edit_mask_callback(mask_str):
            nonlocal obj_to_edit
            global selected_object_id
            try:
                if mask_str:
                    obj_to_edit["mask"] = int(mask_str, 16)
            except ValueError:
                self.update_status("Invalid mask, keeping previous.", "red")
            save_objects_to_file()
            self.opengl_canvas.update()
            selected_object_id = -1 # Deselect after edit (Changed from None)
            self.update_status("Object edited and saved. Deselected object.", "green")
            self._highlight_active_transform_button(None) # Clear any active transform
            self._highlight_active_object_action_button(None) # Clear any active object action
            self._highlight_active_algo_button(None) # Also clear algorithm highlight
            self._highlight_active_style_button(None) # Also clear style highlight

        def edit_thickness_callback(thick_str):
            nonlocal obj_to_edit
            global selected_object_id
            if thick_str.isdigit():
                obj_to_edit["thickness"] = int(thick_str)
            if obj_to_edit["style"] == STYLE_USER_DEFINED:
                self.activate_input_dialog(f"New hex mask (current: 0x{obj_to_edit['mask']:04X}):", edit_mask_callback)
            else:
                save_objects_to_file()
                self.opengl_canvas.update()
                selected_object_id = -1 # Deselect after edit (Changed from None)
                self.update_status("Object edited and saved. Deselected object.", "green")
                self._highlight_active_transform_button(None) # Clear any active transform
                self._highlight_active_object_action_button(None) # Clear any active object action
                self._highlight_active_algo_button(None) # Also clear algorithm highlight
                self._highlight_active_style_button(None) # Also clear style highlight

        def edit_style_callback(style_str):
            nonlocal obj_to_edit
            global selected_object_id
            if style_str.isdigit():
                new_style = int(style_str)
                if new_style in [STYLE_SOLID, STYLE_DOTTED, STYLE_THICK, STYLE_USER_DEFINED]:
                    obj_to_edit["style"] = new_style
                    if obj_to_edit["style"] == STYLE_THICK:
                        self.activate_input_dialog(f"New thickness (current: {obj_to_edit['thickness']}):", edit_thickness_callback)
                    elif obj_to_edit["style"] == STYLE_USER_DEFINED:
                        self.activate_input_dialog(f"New hex mask (current: 0x{obj_to_edit['mask']:04X}):", edit_mask_callback)
                    else:
                        save_objects_to_file()
                        self.opengl_canvas.update()
                        selected_object_id = -1 # Deselect after edit (Changed from None)
                        self.update_status("Object edited and saved. Deselected object.", "green")
                        self._highlight_active_transform_button(None) # Clear any active transform
                        self._highlight_active_object_action_button(None) # Clear any active object action
                        self._highlight_active_algo_button(None) # Also clear algorithm highlight
                        self._highlight_active_style_button(None) # Also clear style highlight
                else:
                    self.update_status("Invalid style. Keeping previous.", "red")
                    save_objects_to_file()
                    self.opengl_canvas.update()
                    selected_object_id = -1 # Deselect if invalid style (Changed from None)
                    self._highlight_active_transform_button(None) # Clear any active transform
                    self._highlight_active_object_action_button(None) # Clear any active object action
                    self._highlight_active_algo_button(None) # Also clear algorithm highlight
                    self._highlight_active_style_button(None) # Also clear style highlight
            else:
                self.update_status("Invalid style input. Keeping previous.", "red")
                save_objects_to_file()
                self.opengl_canvas.update()
                selected_object_id = -1 # Deselect if invalid style input (Changed from None)
                self._highlight_active_transform_button(None) # Clear any active transform
                self._highlight_active_object_action_button(None) # Clear any active object action
                self._highlight_active_algo_button(None) # Also clear algorithm highlight
                self._highlight_active_style_button(None) # Also clear style highlight
            
        def edit_color_callback_dialog():
            nonlocal obj_to_edit
            global selected_object_id

            initial_qcolor = QColor(int(obj_to_edit['color'][0]*255), 
                                    int(obj_to_edit['color'][1]*255), 
                                    int(obj_to_edit['color'][2]*255))
            color = QColorDialog.getColor(initial_qcolor, self, "Pick a Color for Object")

            if color.isValid():
                r, g, b, _ = color.getRgbF()
                obj_to_edit["color"] = (r, g, b)
                r_int, g_int, b_int = int(r*255), int(g*255), int(b*255)
                self.update_status(f"Set object {obj_to_edit['id']} color to: #{r_int:02X}{g_int:02X}{b_int:02X}", "#333333") 
            else:
                self.update_status("Color selection cancelled, keeping previous.", "orange")
            
            current_style_name = {
                STYLE_SOLID: "Solid",
                STYLE_DOTTED: "Dotted",
                STYLE_THICK: "Thick",
                STYLE_USER_DEFINED: "User-defined"
            }.get(obj_to_edit['style'], "Unknown")
            
            self.activate_input_dialog(f"New style (1=Solid, 2=Dotted, 3=Thick, 4=User-defined, current: {current_style_name}):", edit_style_callback)

        edit_color_callback_dialog()
        self._highlight_active_transform_button(None) # Clear any active transform
        self._highlight_active_object_action_button(None) # Clear any active object action
        self._highlight_active_algo_button(None) # Also clear algorithm highlight
        self._highlight_active_style_button(None) # Also clear style highlight


    def delete_selected_object(self):
        global selected_object_id, objects_to_draw
        if selected_object_id != -1: # Changed from None
            objects_to_draw[:] = [obj for obj in objects_to_draw if obj["id"] != selected_object_id]
            selected_object_id = -1 # Changed from None
            save_objects_to_file()
            self.update_status("Object deleted and saved. Deselected object.", "green")
            self.opengl_canvas.update()
            self._highlight_active_transform_button(None) # Clear any active transform
            self._highlight_active_object_action_button(None) # Clear any active object action
            self._highlight_active_algo_button(None) # Also clear algorithm highlight
            self._highlight_active_style_button(None) # Also clear style highlight
        else:
            self.update_status("No object selected to delete.", "red")

    def prompt_rotate(self, button_ref=None): # Added button_ref
        global selected_object_id, current_mode
        if selected_object_id == -1: # Changed from None
            self.update_status("No object selected for rotation.", "red")
            self._highlight_active_transform_button(None) # Clear highlight if no object
            self._highlight_active_algo_button(None) # Also clear algorithm highlight
            self._highlight_active_style_button(None) # Also clear style highlight
            return
        
        obj_to_transform = next((obj for obj in objects_to_draw if obj["id"] == selected_object_id), None)
        if not obj_to_transform:
            self.update_status("Error: Selected object not found for rotation.", "red")
            selected_object_id = -1 # Changed from None
            self.opengl_canvas.update()
            self._highlight_active_transform_button(None) # Clear highlight if object not found
            self._highlight_active_algo_button(None) # Also clear algorithm highlight
            self._highlight_active_style_button(None) # Also clear style highlight
            return

        self._highlight_active_transform_button(button_ref) # Highlight the clicked button
        current_mode = MODE_APPLY_ROTATE # Set the mode for the transformation

        def rotate_callback(angle_str):
            nonlocal obj_to_transform
            global selected_object_id
            try:
                angle = float(angle_str)
                effective_params = apply_transformations(obj_to_transform)
                cx, cy = 0, 0
                if obj_to_transform["type"] in ["circle", "ellipse"]:
                    cx, cy = effective_params["xc"], effective_params["yc"]
                elif obj_to_transform["type"] == "line": # Changed to obj_to_transform["type"] for consistency
                    cx = (effective_params["x1"] + effective_params["x2"]) / 2
                    cy = (effective_params["y1"] + effective_params["y2"]) / 2

                obj_to_transform["transformations"].append({"type": "rotate", "angle": angle, "cx": cx, "cy": cy})
                self.update_status(f"Rotated by {angle} degrees around ({cx:.0f}, {cy:.0f}).", "blue")
                save_objects_to_file()
            except ValueError:
                self.update_status("Invalid angle. Please enter a number.", "red") # More specific error
            selected_object_id = -1 # Deselect after transformation
            self.set_mode(MODE_IDLE, "Idle (after rotation)")
            self._highlight_active_transform_button(None) # Clear highlight after transformation
            self._highlight_active_algo_button(None) # Also clear algorithm highlight
            self._highlight_active_style_button(None) # Also clear style highlight
            self.opengl_canvas.update()
        self.activate_input_dialog("Enter rotation angle (degrees):", rotate_callback)


    def prompt_scale(self, button_ref=None): # Added button_ref
        global selected_object_id, current_mode
        if selected_object_id == -1: # Changed from None
            self.update_status("No object selected for scaling.", "red")
            self._highlight_active_transform_button(None) # Clear highlight if no object
            self._highlight_active_algo_button(None) # Also clear algorithm highlight
            self._highlight_active_style_button(None) # Also clear style highlight
            return

        obj_to_transform = next((obj for obj in objects_to_draw if obj["id"] == selected_object_id), None)
        if not obj_to_transform:
            self.update_status("Error: Selected object not found for scaling.", "red")
            selected_object_id = -1 # Changed from None
            self.opengl_canvas.update()
            self._highlight_active_transform_button(None) # Clear highlight if object not found
            self._highlight_active_algo_button(None) # Also clear algorithm highlight
            self._highlight_active_style_button(None) # Also clear style highlight
            return

        self._highlight_active_transform_button(button_ref) # Highlight the clicked button
        current_mode = MODE_APPLY_SCALE # Set the mode for the transformation

        def scale_y_callback(scale_y_str):
            nonlocal obj_to_transform
            global selected_object_id
            scale_x_str = self.input_dialog_widget.property("scale_x_temp")
            try:
                scale_x = float(scale_x_str)
                scale_y = float(scale_y_str)
                
                effective_params = apply_transformations(obj_to_transform)
                fx, fy = 0, 0
                if obj_to_transform["type"] in ["circle", "ellipse"]:
                    fx, fy = effective_params["xc"], effective_params["yc"]
                elif obj_to_transform["type"] == "line": # Changed to obj_to_transform["type"] for consistency
                    fx = (effective_params["x1"] + effective_params["x2"]) / 2
                    fy = (effective_params["y1"] + effective_params["y2"]) / 2

                obj_to_transform["transformations"].append({"type": "scale", "sx": scale_x, "sy": scale_y, "fx": fx, "fy": fy})
                self.update_status(f"Scaled by ({scale_x}, {scale_y}) around ({fx:.0f}, {fy:.0f}).", "blue")
                save_objects_to_file()
            except ValueError:
                self.update_status("Invalid scale factors. Please enter numbers.", "red") # More specific error
            selected_object_id = -1 # Deselect after transformation
            self.set_mode(MODE_IDLE, "Idle (after scaling)")
            self._highlight_active_transform_button(None) # Clear highlight after transformation
            self._highlight_active_algo_button(None) # Also clear algorithm highlight
            self._highlight_active_style_button(None) # Also clear style highlight
            self.opengl_canvas.update()

        def scale_x_callback(scale_x_str):
            # Validate input for scale_x before proceeding to scale_y
            try:
                float(scale_x_str) # Just try converting to float to validate
                self.input_dialog_widget.setProperty("scale_x_temp", scale_x_str)
                self.activate_input_dialog("Enter Y scale factor:", scale_y_callback)
            except ValueError:
                self.update_status("Invalid X scale factor. Please enter a number.", "red")
                selected_object_id = -1 # Deselect if invalid input
                self.set_mode(MODE_IDLE, "Idle (scale cancelled)")
                self._highlight_active_transform_button(None) # Clear highlight if cancelled
                self._highlight_active_algo_button(None) # Also clear algorithm highlight
                self._highlight_active_style_button(None) # Also clear style highlight
                self.opengl_canvas.update()


        self.activate_input_dialog("Enter X scale factor:", scale_x_callback)


    def prompt_reflect(self, button_ref=None): # Added button_ref
        global selected_object_id, current_mode
        if selected_object_id == -1: # Changed from None
            self.update_status("No object selected for reflection.", "red")
            self._highlight_active_transform_button(None) # Clear highlight if no object
            self._highlight_active_algo_button(None) # Also clear algorithm highlight
            self._highlight_active_style_button(None) # Also clear style highlight
            return

        obj_to_transform = next((obj for obj in objects_to_draw if obj["id"] == selected_object_id), None)
        if not obj_to_transform:
            self.update_status("Error: Selected object not found for reflection.", "red")
            selected_object_id = -1 # Changed from None
            self.opengl_canvas.update()
            self._highlight_active_transform_button(None) # Clear highlight if object not found
            self._highlight_active_algo_button(None) # Also clear algorithm highlight
            self._highlight_active_style_button(None) # Also clear style highlight
            return

        self._highlight_active_transform_button(button_ref) # Highlight the clicked button
        current_mode = MODE_APPLY_REFLECT # Set the mode for the transformation

        def reflect_option_callback(choice_str):
            nonlocal obj_to_transform
            global selected_object_id, current_mode, temp_points

            choice = choice_str.lower()
            if choice == "x" or choice == "1":
                obj_to_transform["transformations"].append({"type": "reflect", "axis": "x"})
                self.update_status("Reflected across X-axis.", "blue")
            elif choice == "y" or choice == "2":
                obj_to_transform["transformations"].append({"type": "reflect", "axis": "y"})
                self.update_status("Reflected across Y-axis.", "blue")
            elif choice == "origin" or choice == "3":
                obj_to_transform["transformations"].append({"type": "reflect", "axis": "origin"})
                self.update_status("Reflected across origin.", "blue")
            elif choice == "line" or choice == "4":
                # User chose arbitrary line reflection, enter the new mode
                current_mode = MODE_APPLY_REFLECT_LINE_P1
                temp_points = [] # Clear any old temp points
                self.update_status("Selected 'Line Reflection'. Click first point (P1) on canvas.", "#333333")
                self.opengl_canvas.update() # Update to show active mode
                selected_object_id = obj_to_transform["id"] # Keep object selected for line definition
                self._highlight_active_transform_button(button_ref) # Keep reflect button highlighted during line definition
                self._highlight_active_algo_button(None) # Also clear algorithm highlight
                self._highlight_active_style_button(None) # Also clear style highlight
                return # Don't reset mode or deselect yet, as we need more clicks
            else:
                self.update_status("Invalid reflection choice. Use 'x', 'y', 'origin', or 'line'.", "red")
            
            # If an axis/origin reflection was applied, reset mode and deselect
            if current_mode != MODE_APPLY_REFLECT_LINE_P1: # Only reset if not entering line selection mode
                selected_object_id = -1 
                self.set_mode(MODE_IDLE, "Idle (after reflection)")
                self._highlight_active_transform_button(None) # Clear highlight after transformation
                self._highlight_active_algo_button(None) # Also clear algorithm highlight
                self._highlight_active_style_button(None) # Also clear style highlight
            
            save_objects_to_file()
            self.opengl_canvas.update()

        self.activate_input_dialog("Reflect across (x/y/origin/line or 1/2/3/4):", reflect_option_callback)


    # --- In-Window Input Dialog (PyQt-based) ---
    def activate_input_dialog(self, prompt, callback):
        self.input_dialog_prompt = prompt
        self.input_dialog_callback = callback
        self.input_dialog_active = True
        
        canvas_top_left_x_on_main = MENU_WIDTH_PX
        canvas_top_left_y_on_main = 0

        canvas_center_x = canvas_top_left_x_on_main + (self.opengl_canvas.width() // 2)
        canvas_center_y = canvas_top_left_y_on_main + (self.opengl_canvas.height() // 2)

        self.input_dialog_widget.setPlaceholderText(prompt)
        self.input_dialog_widget.setText("")
        self.input_dialog_widget.setGeometry(
            canvas_center_x - self.input_dialog_widget.width() // 2,
            canvas_center_y - self.input_dialog_widget.height() // 2,
            200, 30
        )
        self.input_dialog_widget.show()
        self.input_dialog_widget.setFocus()
        self.opengl_canvas.update()

    def handle_input_dialog_text_changed(self, text):
        self.opengl_canvas.update()

    def handle_input_dialog_return_pressed(self):
        if not self.input_dialog_active:
            return

        input_value = self.input_dialog_widget.text()
        self.input_dialog_active = False
        self.input_dialog_widget.hide()
        self.input_dialog_widget.clearFocus()
        self.opengl_canvas.setFocus() # Return focus to canvas
        
        if self.input_dialog_callback:
            self.input_dialog_callback(input_value)
        
        self.opengl_canvas.update()

    def eventFilter(self, obj, event):
        global temp_points, current_mode, selected_object_id
        if obj == self.input_dialog_widget and event.type() == event.KeyPress:
            if event.key() == Qt.Key_Escape:
                if self.input_dialog_active:
                    self.input_dialog_active = False
                    self.input_dialog_widget.hide()
                    self.input_dialog_widget.clearFocus()
                    self.opengl_canvas.setFocus()
                    self.update_status("Input dialog cancelled.", "orange")
                    # If any multi-click drawing or transformation was in progress, clear temp points
                    if current_mode in [MODE_DRAWING_LINE_P1, MODE_DRAWING_LINE_P2,
                                        MODE_DRAWING_CIRCLE_CENTER, MODE_DRAWING_CIRCLE_RADIUS,
                                        MODE_DRAWING_ELLIPSE_CENTER, MODE_DRAWING_ELLIPSE_RX_POINT,
                                        MODE_DRAWING_ELLIPSE_RY_POINT,
                                        MODE_APPLY_TRANSLATE,
                                        MODE_APPLY_REFLECT_LINE_P1, MODE_APPLY_REFLECT_LINE_P2] and temp_points: # Added new reflect modes
                        temp_points.clear()
                        self.update_status(f"Drawing/Operation for mode {current_mode} cancelled.", "orange")
                        selected_object_id = -1 # Also deselect on cancel
                        current_mode = MODE_IDLE # Reset mode
                        self._highlight_active_transform_button(None) # Clear highlight on cancel
                        self._highlight_active_object_action_button(None) # Clear highlight on cancel
                        self._highlight_active_algo_button(None) # Also clear algorithm highlight on cancel
                        self._highlight_active_style_button(None) # Also clear style highlight on cancel
                    self.opengl_canvas.update()
                    return True
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        save_objects_to_file()
        self.update_status("Application closed, objects saved.", "black") # Status text color changed
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
