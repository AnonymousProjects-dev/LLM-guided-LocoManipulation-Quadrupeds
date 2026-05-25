import pygame
import csv
import math
import re
import ast

# ============================================================
# CONFIG
# ============================================================
PIXELS_PER_M = 120
ROOM_W_M = 3.0
ROOM_H_M = 5.0

CSV_FILE = "collected_demos_for_physics_rollouts_filtered.csv"

ROBOT_LENGTH_M = 0.7
ROBOT_WIDTH_M = 0.3

# ============================================================
# PARSING HELPERS
# ============================================================
def get_all_trajectory_ids():
    ids = set()
    with open(CSV_FILE, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ids.add(int(row["trajectory_id"]))
    return sorted(ids)

def parse_robot(s):
    s = s.strip("()")
    parts = s.split(",")
    x = float(parts[0].split("=")[1])
    y = float(parts[1].split("=")[1])
    yaw = math.radians(float(parts[2].split("=")[1]))
    return [x, y, yaw]

def parse_object(s):
    if s.strip() == "":
        return None

    pattern = r'([^,]+),(\d+),(\[.*?\]),\((.*?)\)'
    m = re.match(pattern, s.strip())
    if not m:
        print("WARNING: failed to parse object:", s)
        return None

    typ = m.group(1)
    movable = bool(int(m.group(2)))
    dims = ast.literal_eval(m.group(3))
    pose_raw = m.group(4)

    pose_parts = pose_raw.split(",")
    x = float(pose_parts[0].split("=")[1])
    y = float(pose_parts[1].split("=")[1])
    yaw = math.radians(float(pose_parts[2].split("=")[1]))

    return {
        "type": typ,
        "movable": movable,
        "dims": dims,
        "pos": [x, y, yaw]
    }

# ============================================================
# GENERAL GOAL PARSER
# ============================================================
def parse_goal(task_string):
    clean = task_string.replace(" ", "").lower()

    # MANIPULATION: manipulateobject2to(...)
    m = re.search(
        r"manipulateobject(\d+)to\(x=([\-0-9\.]+),y=([\-0-9\.]+),yaw=([\-0-9\.]+)\)",
        clean
    )
    if m:
        return {
            "mode": "manipulation",
            "target_id": int(m.group(1)),
            "x": float(m.group(2)),
            "y": float(m.group(3)),
            "yaw": math.radians(float(m.group(4)))
        }

    # NAVIGATION: navigaterobotto(...), navigateto(...)
    m = re.search(
        r"navigate(?:robot)?to\(x=([\-0-9\.]+),y=([\-0-9\.]+),yaw=([\-0-9\.]+)\)",
        clean
    )
    if m:
        return {
            "mode": "navigation",
            "target_id": "robot",
            "x": float(m.group(1)),
            "y": float(m.group(2)),
            "yaw": math.radians(float(m.group(3)))
        }

    return None

# ============================================================
# TEXT WRAPPING
# ============================================================
def wrap_text(text, font, max_width):
    words = text.split(" ")
    lines = []
    current = ""
    for w in words:
        test = current + w + " "
        if font.size(test)[0] <= max_width:
            current = test
        else:
            lines.append(current)
            current = w + " "
    if current:
        lines.append(current)
    return lines

# ============================================================
# COORDINATE TRANSFORM
# ============================================================
def world_to_screen(pos, cx, cy):
    return (
        int(cx + pos[0] * PIXELS_PER_M),
        int(cy + pos[1] * PIXELS_PER_M)
    )

# ============================================================
# DRAW GRID + AXES
# ============================================================
def draw_grid(screen, cx, cy):
    grid_color = (210, 210, 210)
    step = int(0.05 * PIXELS_PER_M)

    width = int(ROOM_W_M * PIXELS_PER_M)
    height = int(ROOM_H_M * PIXELS_PER_M)

    x0 = int(cx - width / 2)
    y0 = int(cy - height / 2)

    x = x0
    while x < x0 + width:
        pygame.draw.line(screen, grid_color, (x, y0), (x, y0 + height))
        x += step

    y = y0
    while y < y0 + height:
        pygame.draw.line(screen, grid_color, (x0, y), (x0 + width, y))
        y += step

def draw_axes(screen, cx, cy):
    x_color = (255, 0, 0)
    y_color = (0, 0, 255)

    x0 = cx - ROOM_W_M/2 * PIXELS_PER_M
    x1 = cx + ROOM_W_M/2 * PIXELS_PER_M
    y0 = cy - ROOM_H_M/2 * PIXELS_PER_M
    y1 = cy + ROOM_H_M/2 * PIXELS_PER_M

    pygame.draw.line(screen, x_color, (x0, cy), (x1, cy), 2)
    pygame.draw.line(screen, y_color, (cx, y0), (cx, y1), 2)

    font = pygame.font.SysFont("arial", 16)
    screen.blit(font.render("+X →", True, x_color), (cx + 40, cy + 10))
    screen.blit(font.render("↓ +Y", True, y_color), (cx + 10, cy + 40))

# ============================================================
# LOAD TRAJECTORY
# ============================================================
def load_trajectory(traj_id):
    states = []
    with open(CSV_FILE, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row["trajectory_id"]) == traj_id:
                states.append(row)
    states.sort(key=lambda r: int(r["state_index"]))
    return states

# ============================================================
# DRAW FUNCTIONS
# ============================================================
def draw_arrow(screen, x, y, yaw, color=(0,255,0), length=45, width=5):
    x2 = x + length * math.cos(yaw)
    y2 = y + length * math.sin(yaw)
    pygame.draw.line(screen, color, (x, y), (x2, y2), width)

    ah = 12
    left = (x2 + ah * math.cos(yaw + 2.5),
            y2 + ah * math.sin(yaw + 2.5))
    right = (x2 + ah * math.cos(yaw - 2.5),
             y2 + ah * math.sin(yaw - 2.5))

    pygame.draw.polygon(screen, color, [(x2, y2), left, right])

def draw_robot(screen, robot, cx, cy):
    x, y, yaw = robot
    sx, sy = world_to_screen([x, y], cx, cy)

    w = ROBOT_LENGTH_M * PIXELS_PER_M
    h = ROBOT_WIDTH_M * PIXELS_PER_M

    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill((255, 0, 0, 160))
    rotated = pygame.transform.rotate(surf, -math.degrees(yaw))
    screen.blit(rotated, rotated.get_rect(center=(sx, sy)))

    draw_arrow(screen, sx, sy, yaw, color=(0, 0, 0), length=50, width=5)

def draw_object(screen, obj, cx, cy):
    typ = obj["type"]
    dims = obj["dims"]
    x, y, yaw = obj["pos"]

    # --- NEW: color based on movability ---
    if obj["movable"]:
        color = (80, 180, 80, 180)   # movable → green-ish
        circle_color = (80, 180, 80)
    else:
        color = (160, 160, 160, 180) # unmovable → gray-ish
        circle_color = (160, 160, 160)
    # --------------------------------------

    sx, sy = world_to_screen([x, y], cx, cy)

    if typ == "rect":
        w = dims[0] * PIXELS_PER_M
        h = dims[1] * PIXELS_PER_M
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill(color)
        rotated = pygame.transform.rotate(surf, -math.degrees(yaw))
        screen.blit(rotated, rotated.get_rect(center=(sx, sy)))
    else:
        r = int(dims[0] * PIXELS_PER_M)
        pygame.draw.circle(screen, circle_color, (sx, sy), r)

    # Draw ID label
    font = pygame.font.SysFont("arial", 18)
    screen.blit(
        font.render(str(obj["id"]), True, (0, 0, 0)),
        (sx - 5, sy - 25)
    )

def draw_object_heading(screen, obj, cx, cy):
    x, y, yaw = obj["pos"]
    sx, sy = world_to_screen([x, y], cx, cy)
    # green-ish arrow for object heading
    draw_arrow(screen, sx, sy, yaw, color=(0, 120, 200), length=40, width=4)


# ============================================================
# MAIN VIEWER
# ============================================================
"""def run_viewer(ids, start_index=0):
    idx = start_index
    loaded_tid = ids[idx]

    states = load_trajectory(loaded_tid)
    if not states:
        print(f"[ERROR] Could not load trajectory {loaded_tid}")
        return

    task = states[0]["task"]
    goal = parse_goal(task)

    center_x = 500
    center_y = 450

    action_sequence = [s["actions"].strip() for s in states if s["actions"].strip()]

    pygame.init()
    screen = pygame.display.set_mode((1600, 900))
    font = pygame.font.SysFont("arial", 20)
    small_font = pygame.font.SysFont("arial", 18)

    cur_index = 0
    autoplay = False
    clock = pygame.time.Clock()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                elif event.key == pygame.K_RIGHT:
                    cur_index = min(cur_index + 1, len(states) - 1)

                elif event.key == pygame.K_LEFT:
                    cur_index = max(cur_index - 1, 0)

                elif event.key == pygame.K_SPACE:
                    autoplay = True

                elif event.key == pygame.K_p:
                    autoplay = False

                # ✅ NEXT TRAJECTORY
                elif event.key == pygame.K_UP:
                    idx = min(len(ids) - 1, idx + 1)
                    loaded_tid = ids[idx]
                    states = load_trajectory(loaded_tid)

                    cur_index = 0
                    task = states[0]["task"]
                    goal = parse_goal(task)
                    action_sequence = [s["actions"].strip() for s in states if s["actions"].strip()]

                    print(f"Loaded trajectory {loaded_tid} (index {idx}/{len(ids)-1})")

                # ✅ PREVIOUS TRAJECTORY
                elif event.key == pygame.K_DOWN:
                    idx = max(0, idx - 1)
                    loaded_tid = ids[idx]
                    states = load_trajectory(loaded_tid)

                    cur_index = 0
                    task = states[0]["task"]
                    goal = parse_goal(task)
                    action_sequence = [s["actions"].strip() for s in states if s["actions"].strip()]

                    print(f"Loaded trajectory {loaded_tid} (index {idx}/{len(ids)-1})")

        if autoplay:
            cur_index += 1
            if cur_index >= len(states):
                autoplay = False
                cur_index = len(states) - 1

        st = states[cur_index]
        robot = parse_robot(st["robot"])

        # load objects
        objects = []
        for i in range(1, 21):
            o = parse_object(st[f"object_{i}"])
            if o:
                o["id"] = i
                objects.append(o)

        # drawing -------------------------------------------------
        screen.fill((255,255,255))

        room_px_w = int(ROOM_W_M * PIXELS_PER_M)
        room_px_h = int(ROOM_H_M * PIXELS_PER_M)
        room_x = int(center_x - room_px_w/2)
        room_y = int(center_y - room_px_h/2)

        pygame.draw.rect(screen, (230,230,230),
                         (room_x, room_y, room_px_w, room_px_h))

        draw_grid(screen, center_x, center_y)
        draw_axes(screen, center_x, center_y)

        for o in objects:
            draw_object(screen, o, center_x, center_y)
            draw_object_heading(screen, o, center_x, center_y)

        if goal and goal["mode"] == "manipulation":
            for o in objects:
                if o["id"] == goal["target_id"]:
                    gsx, gsy = world_to_screen([goal["x"], goal["y"]], center_x, center_y)
                    draw_arrow(screen, gsx, gsy, goal["yaw"], color=(0,180,0))
                    pygame.draw.circle(screen, (0,150,0), (gsx, gsy), 6)

        if goal and goal["mode"] == "navigation":
            gsx, gsy = world_to_screen([goal["x"], goal["y"]], center_x, center_y)
            draw_arrow(screen, gsx, gsy, goal["yaw"], color=(0,180,0))
            pygame.draw.circle(screen, (0,150,0), (gsx, gsy), 6)

        draw_robot(screen, robot, center_x, center_y)

        # Sidebar -------------------------------------------------
        pygame.draw.rect(screen, (240,240,250), (830,0,470,800))
        y = 20

        screen.blit(font.render(f"Trajectory {loaded_tid}", True, (0,0,0)), (845,y))
        y += 35

        screen.blit(font.render("Task:", True, (0,0,0)), (845,y)); y += 25
        for ln in wrap_text(task, small_font, 430):
            screen.blit(small_font.render(ln, True, (0,0,0)), (845,y))
            y += 20

        y += 15
        screen.blit(font.render(f"State {cur_index}/{len(states)-1}", True, (0,0,0)), (845,y))
        y += 40

        rx, ry, ryaw = robot
        screen.blit(font.render("Robot:", True, (0,0,0)), (845,y)); y += 25
        screen.blit(small_font.render(
            f"x={rx:.2f}, y={ry:.2f}, yaw={math.degrees(ryaw):.1f}",
            True, (0,0,0)), (845,y))
        y += 30

        screen.blit(font.render("Objects:", True, (0,0,0)), (845,y))
        y += 30

        for o in objects:
            ox, oy, oyaw = o["pos"]
            screen.blit(
                small_font.render(
                    f"ID {o['id']}: {o['type']}, dims={o['dims']}, "
                    f"x={ox:.2f}, y={oy:.2f}, yaw={math.degrees(oyaw):.1f}",
                    True, (0,0,0)),
                (845, y)
            )
            y += 22
            if y > 750:
                break

        screen.blit(font.render("Actions:", True, (0,0,0)), (845,y))
        y += 30

        for act in action_sequence:
            for ln in wrap_text(act, small_font, 430):
                screen.blit(small_font.render(ln, True, (0,0,0)), (845,y))
                y += 20
                if y > 760:
                    break

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()"""
def run_viewer(start_tid):
    
    
    display_tid = start_tid
    loaded_tid = start_tid
    

    # load first valid trajectory
    while True:
        states = load_trajectory(loaded_tid)
        if states:
            break
        loaded_tid += 1

    task = states[0]["task"]
    goal = parse_goal(task)

    center_x = 500
    center_y = 450

    action_sequence = [s["actions"].strip() for s in states if s["actions"].strip()]

    pygame.init()
    screen = pygame.display.set_mode((1600, 900))
    font = pygame.font.SysFont("arial", 20)
    small_font = pygame.font.SysFont("arial", 18)

    cur_index = 0
    autoplay = False
    clock = pygame.time.Clock()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                elif event.key == pygame.K_RIGHT:
                    cur_index = min(cur_index + 1, len(states) - 1)

                elif event.key == pygame.K_LEFT:
                    cur_index = max(cur_index - 1, 0)

                elif event.key == pygame.K_SPACE:
                    autoplay = True

                elif event.key == pygame.K_p:
                    autoplay = False

                elif event.key == pygame.K_DOWN:
                    display_tid = max(0, display_tid - 1)
                    probe = display_tid
                    while probe >= 0:
                        new_states = load_trajectory(probe)
                        if new_states:
                            loaded_tid = probe
                            states = new_states
                            break
                        probe -= 1

                    cur_index = 0
                    task = states[0]["task"]
                    goal = parse_goal(task)
                    action_sequence = [s["actions"].strip() for s in states if s["actions"].strip()]
                    print(f"Loaded trajectory {loaded_tid} (display {display_tid})")

                elif event.key == pygame.K_UP:
                    display_tid += 1
                    probe = display_tid
                    while True:
                        new_states = load_trajectory(probe)
                        if new_states:
                            loaded_tid = probe
                            states = new_states
                            break
                        probe += 1

                    cur_index = 0
                    task = states[0]["task"]
                    goal = parse_goal(task)
                    action_sequence = [s["actions"].strip() for s in states if s["actions"].strip()]
                    print(f"Loaded trajectory {loaded_tid} (display {display_tid})")

        if autoplay:
            cur_index += 1
            if cur_index >= len(states):
                autoplay = False
                cur_index = len(states) - 1

        st = states[cur_index]
        robot = parse_robot(st["robot"])

        # load objects
        objects = []
        for i in range(1, 21):
            o = parse_object(st[f"object_{i}"])
            if o:
                o["id"] = i
                objects.append(o)

        # drawing -------------------------------------------------
        screen.fill((255, 255, 255))

        room_px_w = int(ROOM_W_M * PIXELS_PER_M)
        room_px_h = int(ROOM_H_M * PIXELS_PER_M)
        room_x = int(center_x - room_px_w / 2)
        room_y = int(center_y - room_px_h / 2)

        pygame.draw.rect(screen, (230, 230, 230),
                         (room_x, room_y, room_px_w, room_px_h))

        draw_grid(screen, center_x, center_y)
        draw_axes(screen, center_x, center_y)

        for o in objects:
            draw_object(screen, o, center_x, center_y)
            draw_object_heading(screen, o, center_x, center_y)

        if goal and goal["mode"] == "manipulation":
            for o in objects:
                if o["id"] == goal["target_id"]:
                    gsx, gsy = world_to_screen([goal["x"], goal["y"]], center_x, center_y)
                    draw_arrow(screen, gsx, gsy, goal["yaw"], color=(0, 180, 0))
                    pygame.draw.circle(screen, (0, 150, 0), (gsx, gsy), 6)

        if goal and goal["mode"] == "navigation":
            gsx, gsy = world_to_screen([goal["x"], goal["y"]], center_x, center_y)
            draw_arrow(screen, gsx, gsy, goal["yaw"], color=(0, 180, 0))
            pygame.draw.circle(screen, (0, 150, 0), (gsx, gsy), 6)

        draw_robot(screen, robot, center_x, center_y)

        # Sidebar -------------------------------------------------
        pygame.draw.rect(screen, (240, 240, 250), (830, 0, 470, 800))
        y = 20

        screen.blit(font.render(f"Trajectory {loaded_tid}", True, (0, 0, 0)), (845, y))
        y += 35

        screen.blit(font.render("Task:", True, (0, 0, 0)), (845, y))
        y += 25
        for ln in wrap_text(task, small_font, 430):
            screen.blit(small_font.render(ln, True, (0, 0, 0)), (845, y))
            y += 20

        y += 15
        screen.blit(font.render(f"State {cur_index}/{len(states) - 1}", True, (0, 0, 0)), (845, y))
        y += 40

        rx, ry, ryaw = robot
        screen.blit(font.render("Robot:", True, (0, 0, 0)), (845, y))
        y += 25
        screen.blit(
            small_font.render(f"x={rx:.2f}, y={ry:.2f}, yaw={math.degrees(ryaw):.1f}", True, (0, 0, 0)),
            (845, y)
        )
        y += 30

        screen.blit(font.render("Objects:", True, (0, 0, 0)), (845, y))
        y += 30

        for o in objects:
            ox, oy, oyaw = o["pos"]
            screen.blit(
                small_font.render(
                    f"ID {o['id']}: {o['type']}, dims={o['dims']}, "
                    f"x={ox:.2f}, y={oy:.2f}, yaw={math.degrees(oyaw):.1f}",
                    True, (0, 0, 0)
                ),
                (845, y)
            )
            y += 22
            if y > 750:
                break

        screen.blit(font.render("Actions:", True, (0, 0, 0)), (845, y))
        y += 30

        for act in action_sequence:
            for ln in wrap_text(act, small_font, 430):
                screen.blit(small_font.render(ln, True, (0, 0, 0)), (845, y))
                y += 20
                if y > 760:
                    break

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()
# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    
    print("Available trajectory IDs:")
    ids = get_all_trajectory_ids()
    print(ids[:10], "..." if len(ids) > 10 else "")

    print("\nEnter trajectory ID to view (leave empty for first available):")

    user_input = input("> ").strip()

    if user_input == "":
        tid = ids[0]
    else:
        try:
            tid = int(user_input)
        except ValueError:
            print("Invalid input. Using first available trajectory.")
            tid = ids[0]

    run_viewer(tid)
"""if __name__ == "__main__":
    ids = [36, 79, 91, 95, 102, 105, 192, 229, 242, 268, 312, 346, 348, 390, 460, 528, 556, 606, 691, 828, 837, 855, 878, 902, 907, 1373, 1383, 1426, 1442, 1452, 1492, 1574, 1637, 1649, 1688, 1740, 1764, 1800, 1809, 1862, 1872, 1885, 1897, 1937, 1967, 1972, 1982, 1986, 1991, 1997, 2006, 2049, 2104, 2133, 2142, 2242, 2262, 2318, 2345, 2368, 2433, 2446, 2452, 2472, 2496, 2502, 2507, 2598, 2600, 2702, 2810, 2818, 2929, 2968, 2971, 3006, 3049, 3104, 3133, 3142, 3242, 3262, 3318, 3345, 3368, 3433, 3446, 3452, 3472, 3496, 3502, 3507, 3598, 3600, 3702, 3810, 3818, 3929, 3968, 3971, 4006, 4049, 4104, 4133, 4142, 4242, 4262, 4318, 4345, 4368, 4433, 4446, 4452, 4472, 4496, 4502, 4507, 4598, 4600, 4702, 4810, 4818, 4929, 4968, 4971, 5006, 5049, 5104, 5133, 5142, 5242, 5262, 5318, 5345, 5368, 5433, 5446, 5452, 5472, 5496, 5502, 5507, 5598, 5600, 5702, 5810, 5818, 5929, 5968, 5971, 6006, 6049, 6104, 6133, 6142, 6242, 6262, 6318, 6345, 6368, 6433, 6446, 6452, 6472, 6496, 6502, 6507, 6598, 6600, 6702, 6810, 6818, 6929, 6968, 6971, 7006, 7049, 7104, 7133, 7142, 7242, 7262, 7318, 7345, 7368, 7433, 7446, 7452, 7472, 7496, 7502, 7507, 7598, 7600, 7702, 7810, 7818, 7929, 7968, 7971]


    print("Sampled trajectory IDs:")
    print(ids)

    run_viewer(ids, start_index=0)
if __name__ == "__main__":
    ids = sorted(get_all_trajectory_ids())

    print("Available trajectory IDs:")
    print(ids[:10], "..." if len(ids) > 10 else "")

    run_viewer(ids, start_index=0)"""