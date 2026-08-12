import pygame
from pygame.locals import *
import numpy as np

# Initialize pygame
pygame.init()
width, height = 800, 600
screen = pygame.display.set_mode((width, height), DOUBLEBUF | OPENGL)
pygame.display.set_caption("Minecraft Python Edition")

# Hide the mouse cursor
pygame.mouse.set_visible(False)

# OpenGL imports
from OpenGL.GL import *
from OpenGL.GLU import *

# Define cube vertices and faces
vertices = [
    [1, 1, -1],
    [1, -1, -1],
    [-1, -1, -1],
    [-1, 1, -1],
    [1, 1, 1],
    [1, -1, 1],
    [-1, -1, 1],
    [-1, 1, 1]
]

faces = [
    (0, 1, 2, 3),  # Front
    (3, 2, 6, 7),  # Left
    (7, 6, 5, 4),  # Back
    (4, 5, 1, 0),  # Right
    (1, 5, 6, 2),  # Bottom
    (4, 0, 3, 7)   # Top
]

# Neighbor offsets for face culling
neighbor_offsets = [
    (0, 0, -1),  # Front
    (-1, 0, 0),  # Left
    (0, 0, 1),   # Back
    (1, 0, 0),   # Right
    (0, -1, 0),  # Bottom
    (0, 1, 0)    # Top
]

# Set background color
glClearColor(0.678, 0.847, 0.902, 1)

# Perspective and initial view
gluPerspective(45, (width / height), 0.1, 50.0)
glTranslatef(0.0, -10.0, -30)  # Initial distance and height

# Camera movement variables
camera_pos = np.array([0.0, 30.0, 0.0])
camera_rot = np.array([0.0, 0.0])
mouse_sensitivity = 0.3
movement_speed = 1
ray_length = 64

# Create a grid to store the presence of cubes
grid_size = 16
grid = np.ones((grid_size, 1, grid_size))  # Initialize all positions with cubes

def draw_cube(x, y, z, highlight=False):
    glPushMatrix()  # Push the current matrix onto the stack
    glTranslatef(x * 2, y * 2, z * 2)  # Adjust the cube position based on x, y, and z coordinates
    for i, face in enumerate(faces):
        nx, ny, nz = x + neighbor_offsets[i][0], y + neighbor_offsets[i][1], z + neighbor_offsets[i][2]
        # Adjust the culling conditions to ensure top and bottom faces are correctly drawn
        if (0 <= nx < grid_size and 0 <= ny < 1 and 0 <= nz < grid_size and grid[nx, ny, nz] == 1) and (i not in [4, 5]):
            continue  # Skip drawing this face if a neighboring cube exists

        glBegin(GL_QUADS)
        for vertex in face:
            if i == 5:  # Top face
                glColor3fv((0.3, 0.8, 0.3))  # Lighter shade of green
            elif i == 4:  # Bottom face
                glColor3fv((0.1, 0.3, 0.1))  # Darker shade of green
            else:  # Other faces
                glColor3fv((0.1, 0.5, 0.1))  # Dark gray
            glVertex3fv(vertices[vertex])
        glEnd()

    glPopMatrix()  # Restore the previous matrix from the stack

def highlight_face(x, y, z, face_index):
    glPushMatrix()
    glTranslatef(x * 2, y * 2, z * 2)
    glColor3f(0, 0, 0)  # Black color for the edges
    glLineWidth(3)  # Thicker line width for better visibility

    face = faces[face_index]
    glBegin(GL_LINE_LOOP)
    for vertex in face:
        glVertex3fv(vertices[vertex])
    glEnd()
    glPopMatrix()

def get_camera_vectors():
    # Calculate forward, right, and up vectors based on camera rotation
    pitch = np.radians(camera_rot[0])
    yaw = np.radians(camera_rot[1])
    
    forward = np.array([
        np.cos(pitch) * np.sin(yaw),
        np.sin(pitch),
        np.cos(pitch) * np.cos(yaw)
    ])
    
    right = np.array([
        np.sin(yaw - np.pi/2),
        0,
        np.cos(yaw - np.pi/2)
    ])
    
    up = np.cross(right, forward)
    
    return forward, right, up

def ray_box_intersection(ray_origin, ray_direction, box_min, box_max, max_distance):
    ray_direction = np.where(ray_direction == 0, 1e-8, ray_direction)
    inv_dir = 1 / ray_direction
    t1 = (box_min - ray_origin) * inv_dir
    t2 = (box_max - ray_origin) * inv_dir

    tmin = np.maximum(np.minimum(t1, t2), 0)
    tmax = np.minimum(np.maximum(t1, t2), max_distance)

    t_enter = np.max(tmin)
    t_exit = np.min(tmax)

    if t_enter > t_exit or t_exit < 0:
        return False, None, None

    intersection = ray_origin + t_enter * ray_direction
    face_index = np.argmax(tmin)

    return True, intersection, face_index

def place_block_on_face(block_pos, face_index):
    # Calculate the position of the new block
    new_block_pos = np.array(block_pos) + np.array(neighbor_offsets[face_index])

    # Place the new block if within bounds
    if 0 <= new_block_pos[0] < grid_size and 0 <= new_block_pos[1] < 1 and 0 <= new_block_pos[2] < grid_size:
        grid[new_block_pos[0], new_block_pos[1], new_block_pos[2]] = 1

# Main loop
clock = pygame.time.Clock()
running = True
mouse_locked = True  # Initial mouse lock state
crosshair_color = (100, 100, 100)  # Dark gray color
crosshair_size = 10
crosshair_thickness = 2
min_scale_factor = 0.001  # Minimum scale factor to keep the cube visible
max_scale_factor = 2.0  # Maximum scale factor

highlighted_face = None  # Track the currently highlighted face
highlighted_block = None  # Track the currently highlighted block

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                pygame.mouse.set_visible(True)
                mouse_locked = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left mouse button
                pygame.mouse.set_visible(False)
                mouse_locked = True
                closest_distance = float('inf')  # Initialize with a large value
                closest_block = None
                for x in range(grid_size):
                    for y in range(1):  # Only one layer of cubes
                        for z in range(grid_size):
                            if grid[x, y, z] == 1:
                                cube_min = np.array([x * 2 - 1, y * 2 - 1, z * 2 - 1])
                                cube_max = np.array([x * 2 + 1, y * 2 + 1, z * 2 + 1])
                                intersection_found, intersection, face_index = ray_box_intersection(camera_pos, forward, cube_min, cube_max, ray_length)
                                if intersection_found:
                                    distance = np.linalg.norm(intersection - camera_pos)
                                    if distance < closest_distance:
                                        closest_distance = distance
                                        closest_block = (x, y, z)
                if closest_block:
                    x, y, z = closest_block
                    grid[x, y, z] = 0  # Remove the closest block from the grid
            elif event.button == 3:  # Right mouse button
                if highlighted_block is not None and highlighted_face is not None:
                    place_block_on_face(highlighted_block, highlighted_face)


    # Lock or unlock the mouse
    if mouse_locked:
        pygame.event.set_grab(True)
    else:
        pygame.event.set_grab(False)

    # Handle keyboard inputs
    keys = pygame.key.get_pressed()
    forward, right, up = get_camera_vectors()
    if keys[pygame.K_w]:
        camera_pos += movement_speed * forward
    elif keys[pygame.K_s]:
        camera_pos -= movement_speed * forward

    if keys[pygame.K_a]:
        camera_pos -= movement_speed * right
    elif keys[pygame.K_d]:
        camera_pos += movement_speed * right

    if keys[pygame.K_SPACE]:
        camera_pos += movement_speed * up
    elif keys[pygame.K_LSHIFT]:
        camera_pos -= movement_speed * up

    # Handle mouse inputs
    if mouse_locked:
        mouse_movement = pygame.mouse.get_rel()
        camera_rot[1] -= mouse_movement[0] * mouse_sensitivity
        camera_rot[0] -= mouse_movement[1] * mouse_sensitivity

        # Constrain the camera pitch (up/down rotation)
        camera_rot[0] = max(-89.0, min(89.0, camera_rot[0]))

    # Clear screen
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    # Apply camera transformations
    glLoadIdentity()
    forward, right, up = get_camera_vectors()
    camera_look_at = camera_pos + forward
    gluLookAt(camera_pos[0], camera_pos[1], camera_pos[2],
            camera_look_at[0], camera_look_at[1], camera_look_at[2],
            up[0], up[1], up[2])

    # Draw cubes
    glPushMatrix()  # Push the current matrix onto the stack
    glEnable(GL_DEPTH_TEST)  # Enable depth testing
    highlighted_face = None
    highlighted_block = None
    face_index = None
    for x in range(grid_size):
        for y in range(1):  # Adjusted for y coordinate
            for z in range(grid_size):
                if grid[x, y, z] == 1:
                    # Define the min and max corners of the current cube
                    box_min = np.array([x * 2 - 1, y * 2 - 1, z * 2 - 1])
                    box_max = np.array([x * 2 + 1, y * 2 + 1, z * 2 + 1])

                    # Check if the ray intersects this cube within the ray length
                    intersects, intersection, face_index = ray_box_intersection(camera_pos, forward, box_min, box_max, ray_length)
                    if intersects:
                        highlighted_face = face_index  # Assign only the face index
                        highlighted_block = (x, y, z)

                    draw_cube(x, y, z)

    glPopMatrix()  # Restore the previous matrix from the stack
    glDisable(GL_DEPTH_TEST)  # Disable depth testing

    # Highlight the intersected face with black edges
    if highlighted_face and face_index is not None:
        x, y, z = highlighted_face
        highlight_face(x, y, z, face_index)

    # Define crosshair position based on camera orientation and distance
    crosshair_distance = 10  # Distance from camera to crosshair
    crosshair_position = camera_pos + forward * crosshair_distance

    # Draw crosshair
    glLoadIdentity()
    gluLookAt(camera_pos[0], camera_pos[1], camera_pos[2],
            crosshair_position[0], crosshair_position[1], crosshair_position[2],
            up[0], up[1], up[2])
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(45, (width / height), 0.1, 50.0)  # Restore perspective projection
    glMatrixMode(GL_MODELVIEW)

    # Calculate position of crosshair on screen
    crosshair_screen_x = width // 2
    crosshair_screen_y = height // 2

    # Sample the color of the pixel under the crosshair
    sample_size = 5  # Adjust the sample size as needed
    total_color = [0, 0, 0]
    num_samples = 0  # Track the number of valid samples
    for dx in range(-sample_size // 2, sample_size // 2 + 1):
        for dy in range(-sample_size // 2, sample_size // 2 + 1):
            data = glReadPixels(crosshair_screen_x + dx, height - crosshair_screen_y + dy, 1, 1, GL_RGB, GL_UNSIGNED_BYTE)
            if data is not None:
                total_color[0] += data[0]
                total_color[1] += data[1]
                total_color[2] += data[2]
                num_samples += 1

    # Calculate the average color
    if num_samples > 0:
        average_color = (total_color[0] // num_samples, total_color[1] // num_samples, total_color[2] // num_samples)
    else:
        # Set a default color if no valid samples are found
        average_color = (255, 255, 255)  # White crosshair as fallback

    # Invert the average color to determine the color of the crosshair
    inverted_color = (255 - average_color[0], 255 - average_color[1], 255 - average_color[2])

    # Draw crosshair with inverted color
    glLoadIdentity()
    gluLookAt(camera_pos[0], camera_pos[1], camera_pos[2],
            crosshair_position[0], crosshair_position[1], crosshair_position[2],
            up[0], up[1], up[2])
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(45, (width / height), 0.1, 50.0)  # Restore perspective projection
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, width, height, 0)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glColor3ub(inverted_color[0], inverted_color[1], inverted_color[2])
    glLineWidth(crosshair_thickness)
    glBegin(GL_LINES)
    glVertex2f(crosshair_screen_x - crosshair_size, crosshair_screen_y)
    glVertex2f(crosshair_screen_x + crosshair_size, crosshair_screen_y)
    glVertex2f(crosshair_screen_x, crosshair_screen_y - crosshair_size)
    glVertex2f(crosshair_screen_x, crosshair_screen_y + crosshair_size)
    glEnd()
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()

    # Draw ray line
    ray_end_pos = camera_pos + forward * ray_length
    cylinder_radius = 0 # Adjust the radius to be larger than the crosshair size

    # Create a new quadric object
    quadric = gluNewQuadric()

    glLoadIdentity()
    gluLookAt(camera_pos[0], camera_pos[1], camera_pos[2],
            camera_look_at[0], camera_look_at[1], camera_look_at[2],
            up[0], up[1], up[2])
    glColor3f(0, 0, 0)  # Red color for the ray line

    # Save the current matrix
    glPushMatrix()
    # Translate to the camera position
    glTranslatef(camera_pos[0], camera_pos[1], camera_pos[2])
    # Rotate the cylinder to align with the camera's forward direction
    angle = np.degrees(np.arccos(np.dot(forward, [0, 0, 1]) / np.linalg.norm(forward)))
    axis = np.cross([0, 0, 1], forward)
    glRotatef(angle, axis[0], axis[1], axis[2])
    # Draw the cylinder
    gluCylinder(quadric, cylinder_radius, cylinder_radius, ray_length, 32, 1)
    # Restore the previous matrix
    glPopMatrix()

    pygame.display.flip()
    clock.tick(60)
pygame.quit()
