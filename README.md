# PyQt5 & OpenGL 2D Graphics Editor 🎨

A mini-project demonstrating an interactive 2D graphics application built with Python, PyQt5 for the GUI, and PyOpenGL for rendering. This application allows users to draw various shapes using classic graphics algorithms, apply transformations, style them, and save their work.


<img width="1176" height="961" alt="image" src="https://github.com/user-attachments/assets/50a8647c-a538-4e2c-a0e2-4f4a97875fde" />





---

## ✨ Features

### 🖌️ Drawing & Algorithms
- **Line Drawing:** Implements three fundamental line-drawing algorithms:
    - **Simple DDA (Digital Differential Analyzer)**
    - **Bresenham's Line Algorithm**
    - **Symmetrical DDA**
- **Shape Drawing:**
    - **Midpoint Circle Algorithm**
    - **Midpoint Ellipse Algorithm**
- **Interactive Drawing:** Draw objects directly on the canvas with mouse clicks.

### 🎨 Styling & Appearance
- **Color Selection:** A pop-up color picker to choose any color for new objects.
- **Line & Shape Styles:**
    - **Solid:** The default continuous line.
    - **Dotted:** A simple dashed line pattern.
    - **Thick:** Draw objects with a user-defined integer thickness. The implementation for thick lines uses a filled `GL_QUAD` for precision.
    - **User-Defined Mask:** Create custom stippled patterns using a 16-bit hexadecimal mask (e.g., `F0F0`).
- **Light UI Theme:** A clean and modern light-mode interface for better readability.

### 🔄 Transformations
Apply a series of transformations to any selected object. Transformations are stacked and applied in order.
- **Translate:** Move an object by defining a start and end point on the canvas.
- **Rotate:** Rotate an object around its calculated center by a specified angle in degrees.
- **Scale:** Scale an object from its center using separate X and Y factors.
- **Reflect:** Mirror an object across the X-axis, Y-axis, or the origin.

### 📦 Object Management
- **Object Selection:** A robust selection mechanism that accurately detects clicks near an object's boundary, accounting for its style and thickness.
- **Object Editing:**
    - **Bake Transformations:** Before editing, all existing transformations are "baked" into the object's base parameters, allowing for intuitive edits and new transformations.
    - Sequentially edit a selected object's **color**, **style**, **thickness**, and **mask**.
- **Delete Object:** Remove any selected object from the canvas.

### 💾 Persistence
- **Auto-Save/Load:** All drawn objects, along with their styles and transformations, are automatically saved to a `graphics_data.json` file on exit or after a new object is created.
- **Session Restoration:** The application automatically reloads all objects from the JSON file on startup, preserving your work between sessions.

### 🖥️ Canvas & UI
- **OpenGL Canvas:** All rendering is handled efficiently by an OpenGL widget.
- **Coordinate System:** A logical Cartesian coordinate system with the origin `(0,0)` at the center of the canvas.
- **Toggleable Grid:** Display a background grid for better alignment and visualization.
- **Grid Snapping:** All mouse clicks for drawing and transformations are automatically snapped to the nearest grid intersection, ensuring clean and precise placements.
- **Status Bar:** Provides real-time feedback to the user about the current mode, actions taken, and next steps.
- **In-Window Input:** Custom, non-blocking input dialogs appear over the canvas for entering values like angles or thickness, providing a seamless user experience.

---

## 🚀 Getting Started

Follow these instructions to get the project running on your local machine.

### Prerequisites
- **Python 3.x**
- **pip** (Python package installer)

### Installation
1.  **Clone the repository or download the graphics_editor.py` file.**

2.  **Install the required Python libraries using pip:**
    ```bash
    pip install PyQt5 PyOpenGL PyOpenGL_accelerate
    ```

### Running the Application
1.  **Navigate to the directory containing the `graphics_editor.py` file.**

2.  **Run the script from your terminal:**
    ```bash
    python graphics_editor.py
    ```
The application window should now appear.

---

## 📖 How to Use

### Drawing a Shape
1.  **Select an Algorithm:** Click on a drawing algorithm from the "ALGORITHM" section in the left menu (e.g., "Bresenham Line"). The button will highlight in green, and the status bar will prompt you for the next action.
2.  **Set Style (Optional):** Choose a style ("Solid", "Dotted", etc.) and pick a color before drawing. If you select "Thick" or "User-Def", an input box will appear on the canvas to enter the required value.
3.  **Draw on the Canvas:**
    - For a **line**, click once to set the start point (P1) and click a second time to set the end point (P2).
    - For a **circle**, click once for the center and a second time to define the radius.
    - For an **ellipse**, click three times: once for the center, a second time to define the X-radius, and a third time to define the Y-radius.
4.  The shape will appear on the canvas, and your work is automatically saved.

### Selecting and Transforming an Object
1.  **Enter Selection Mode:** Click the **"Select Object"** button in the "OBJECT ACTIONS" section.
2.  **Click on an Object:** Click near the boundary of any shape on the canvas. If successful, the object will be highlighted in yellow, and the status bar will confirm the selection.
3.  **Choose a Transformation:**
    - Click **"Translate"**: Click a start point and an end point on the canvas to move the object.
    - Click **"Rotate"**, **"Scale"**, or **"Reflect"**: An input dialog will appear over the canvas. Enter the required parameters (e.g., angle, scale factors) and press Enter.
4.  The transformation is applied, and the object is deselected. Your changes are saved.

### Editing an Object
1.  **Select an object** as described above.
2.  Click the **"Edit Selected"** button.
3.  A series of input dialogs and a color picker will guide you through changing the object's properties (color, style, thickness, etc.).
4.  After editing, the object is updated and deselected.

---

## 🛠️ Technical Overview

### Core Components
- **`MainWindow` (QMainWindow):** The main application window that hosts the UI menu and the OpenGL canvas. It manages UI state, button connections, and the input dialog system.
- **`OpenGLCanvas` (QOpenGLWidget):** The core rendering area. It handles all OpenGL drawing calls (`paintGL`), manages the viewport and coordinate systems (`resizeGL`), and processes user mouse and keyboard events for drawing and interaction.

### Coordinate System
The application internally uses a **logical coordinate system** where `(0, 0)` is the center of the canvas. The `logical_to_screen()` and `screen_to_logical()` helper functions handle the conversion between this system and the **screen's pixel coordinate system** (where `(0, 0)` is the top-left corner). This separation makes geometric calculations much more intuitive.

### State Management
- A global `current_mode` variable tracks the application's state (e.g., `MODE_DRAWING_LINE_P1`, `MODE_APPLY_TRANSLATE`).
- This state machine dictates how mouse clicks are interpreted by the `mousePressEvent` handler in the `OpenGLCanvas` class.
- Other global variables manage the current drawing settings (color, style, algorithm) and the list of objects.

### Data Persistence (`graphics_data.json`)
- All objects are stored in a list of dictionaries (`objects_to_draw`).
- Each dictionary contains the object's ID, type, drawing parameters, style information, and a list of applied transformations.
- The `save_objects_to_file()` function serializes this list into a human-readable JSON file. The function `load_objects_from_file()` performs the reverse operation on startup.

### Transformation Logic
- Transformations are not immediately applied to an object's base parameters. Instead, they are stored as a list within the object's dictionary.
- During each render cycle (`paintGL`), the `apply_transformations()` function calculates the *effective* parameters of an object by iterating through its transformation list. This allows transformations to be stacked and preserved.
- When an object is edited, these transformations are "baked" into the base parameters, and the transformation list is cleared, setting a new baseline for the object's state.

---

## 👨‍💻 Author
Developed as a **Mini Computer Graphics Project** using PyQt5 and OpenGL.

Feel free to fork and contribute 🚀

---

## 📜 License
This project is open-source under the **MIT License**.
