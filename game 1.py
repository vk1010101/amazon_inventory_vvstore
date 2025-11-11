import pygame, random, sys

pygame.init()

# ---------- Setup ----------
WIDTH, HEIGHT = 1500, 900
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Vanshul: The Verma Legacy – Puzzle Escape")

clock = pygame.time.Clock()

# ---------- Colors ----------
WHITE = (255, 255, 255)
BLUE = (80, 160, 255)
GOLD = (255, 215, 0)
RED = (255, 80, 80)
BLACK = (0, 0, 0)
GREEN = (0, 255, 120)
PURPLE = (180, 60, 255)
GRAY = (70, 70, 70)

# ---------- Player (Vanshul) ----------
player_size = 60
player_pos = [WIDTH//2, HEIGHT-150]
player_speed = 18   # 🚀 Faster Vanshul
player_health = 100

# ---------- Boss (Raka) ----------
raka_size = 80
raka_pos = [random.randint(50, WIDTH-50), 50]
raka_base_speed = 4

# ---------- Levels & Puzzle Setup ----------
current_level = 1
max_level = 3
puzzle_triggered = False
font = pygame.font.Font(None, 38)
bigfont = pygame.font.Font(None, 72)

# ---------- Maze Barriers ----------
def generate_barriers():
    barriers = []
    for i in range(15):
        barriers.append(pygame.Rect(random.randint(100, WIDTH-300),
                                    random.randint(100, HEIGHT-300),
                                    random.randint(120, 250), 30))
    return barriers

barriers = generate_barriers()

# ---------- Puzzle Zone ----------
puzzle_zone = pygame.Rect(WIDTH//2 - 150, 100, 300, 150)

# ---------- Puzzle List ----------
puzzles = [
    ("I’m tall when I’m young and short when I’m old. What am I?", "candle"),
    ("The more you take, the more you leave behind. What am I?", "footsteps"),
    ("What has keys but can’t open locks?", "piano"),
]

# ---------- Helper Functions ----------
def draw_player():
    pygame.draw.ellipse(screen, BLUE, (player_pos[0], player_pos[1], player_size, player_size))
    pygame.draw.circle(screen, GOLD, (player_pos[0]+30, player_pos[1]-10), 20)
    pygame.draw.rect(screen, BLACK, (player_pos[0]+15, player_pos[1]-15, 30, 5))

def draw_raka():
    pygame.draw.ellipse(screen, RED, (raka_pos[0], raka_pos[1], raka_size, raka_size))
    pygame.draw.circle(screen, BLACK, (raka_pos[0]+40, raka_pos[1]-5), 25)
    pygame.draw.rect(screen, PURPLE, (raka_pos[0]+20, raka_pos[1]-15, 40, 5))

def draw_barriers():
    for b in barriers:
        pygame.draw.rect(screen, GRAY, b)

def draw_ui():
    health_text = font.render(f"Health: {player_health}", True, WHITE)
    level_text = font.render(f"Level: {current_level}", True, GOLD)
    screen.blit(health_text, (20, 20))
    screen.blit(level_text, (20, 60))

def show_puzzle(question, answer):
    user_answer = ""
    active = True

    while active:
        screen.fill((20, 20, 50))
        title = bigfont.render(f"Level {current_level} Puzzle", True, GOLD)
        question_text = font.render(question, True, WHITE)
        input_text = font.render(user_answer, True, GREEN)
        screen.blit(title, (WIDTH//2 - 200, HEIGHT//2 - 250))
        screen.blit(question_text, (WIDTH//2 - 600, HEIGHT//2 - 100))
        screen.blit(input_text, (WIDTH//2 - 100, HEIGHT//2))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    if user_answer.strip().lower() == answer:
                        win_text = bigfont.render("✅ Correct! Escaping to next level...", True, GREEN)
                        screen.blit(win_text, (WIDTH//2 - 350, HEIGHT//2 + 100))
                        pygame.display.flip()
                        pygame.time.delay(2000)
                        return True
                    else:
                        lose_text = bigfont.render("❌ Wrong Answer! Raka Caught You!", True, RED)
                        screen.blit(lose_text, (WIDTH//2 - 350, HEIGHT//2 + 100))
                        pygame.display.flip()
                        pygame.time.delay(2500)
                        pygame.quit()
                        sys.exit()
                elif event.key == pygame.K_BACKSPACE:
                    user_answer = user_answer[:-1]
                else:
                    user_answer += event.unicode
        pygame.display.flip()
        clock.tick(30)

# ---------- Main Loop ----------
running = True
while running:
    # Dynamic level color
    if current_level == 1:
        screen.fill((30, 30, 80))
    elif current_level == 2:
        screen.fill((20, 60, 40))
    else:
        screen.fill((60, 20, 20))

    draw_barriers()
    pygame.draw.rect(screen, (0, 120, 255), puzzle_zone)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

    # Movement
    keys = pygame.key.get_pressed()
    move_x = move_y = 0
    if keys[pygame.K_LEFT] or keys[pygame.K_a]:
        move_x = -player_speed
    if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
        move_x = player_speed
    if keys[pygame.K_UP] or keys[pygame.K_w]:
        move_y = -player_speed
    if keys[pygame.K_DOWN] or keys[pygame.K_s]:
        move_y = player_speed

    # Move player with collision
    new_pos = player_pos.copy()
    new_pos[0] += move_x
    new_pos[1] += move_y
    player_rect = pygame.Rect(new_pos[0], new_pos[1], player_size, player_size)
    colliding = any(player_rect.colliderect(b) for b in barriers)

    if not colliding and 0 < new_pos[0] < WIDTH - player_size and 0 < new_pos[1] < HEIGHT - player_size:
        player_pos = new_pos

    # Boss chase logic
    raka_speed = raka_base_speed + current_level + (player_health // 30)
    if player_pos[0] < raka_pos[0]:
        raka_pos[0] -= raka_speed
    elif player_pos[0] > raka_pos[0]:
        raka_pos[0] += raka_speed
    if player_pos[1] < raka_pos[1]:
        raka_pos[1] -= raka_speed
    elif player_pos[1] > raka_pos[1]:
        raka_pos[1] += raka_speed

    raka_rect = pygame.Rect(raka_pos[0], raka_pos[1], raka_size, raka_size)
    if player_rect.colliderect(raka_rect):
        player_health -= 1

    # Puzzle Trigger
    if player_rect.colliderect(puzzle_zone) and not puzzle_triggered:
        puzzle_triggered = True
        q, a = puzzles[current_level - 1]
        correct = show_puzzle(q, a)
        if correct:
            current_level += 1
            if current_level > max_level:
                win = bigfont.render("🏆 Vanshul Escaped Raka Forever!", True, GOLD)
                screen.fill((0, 0, 0))
                screen.blit(win, (WIDTH//2 - 400, HEIGHT//2))
                pygame.display.flip()
                pygame.time.delay(4000)
                pygame.quit()
                sys.exit()
            else:
                player_pos = [WIDTH//2, HEIGHT-150]
                raka_pos = [random.randint(50, WIDTH-50), 50]
                barriers = generate_barriers()
                puzzle_triggered = False
                continue

    # Health check
    if player_health <= 0:
        over_text = bigfont.render("Game Over! Raka Wins!", True, RED)
        screen.blit(over_text, (WIDTH//2 - 300, HEIGHT//2))
        pygame.display.flip()
        pygame.time.delay(2500)
        pygame.quit()
        sys.exit()

    draw_player()
    draw_raka()
    draw_ui()

    pygame.display.flip()
    
    clock.tick(30)
