import pygame, sys, random, math, time

# -------- CONFIG --------
SCREEN_WIDTH, SCREEN_HEIGHT = 1200, 720
WORLD_WIDTH, WORLD_HEIGHT = 2400, 1600
FPS = 60
PLAYER_SPEED = 8
SNAKE_SPEED = 1.2
NUM_KEYS = 8
PLAYER_MAX_HEALTH = 5

# Colors
WHITE=(255,255,255); BLACK=(0,0,0)
RED=(210,50,50); DARKRED=(150,0,0)
GOLD=(235,192,66); PURPLE=(160,60,200)
DARKGRAY=(40,40,40); LIGHTGRAY=(150,150,150)
GREEN=(60,180,80); SKY_BOTTOM=(100,180,250)
TEAL=(20,150,160)
ROAD=(50,50,50); ROAD_LINES=(220,220,220)
BUILDING=(80,80,80); WINDOW=(200,200,100)
HOME=(180,120,90); TREE=(20,120,40)
BULLET_COLOR=(255,255,0)

# Characters (only 5 now)
CHARACTERS=["Stefan","Damon","Elena","Vanshul","Caroline"]
CHAR_COLORS=[(200,0,0),(0,200,0),(0,0,200),(200,200,0),(200,0,200)]

# -------- UTILITIES --------
def clamp(v,a,b): return max(a,min(b,v))
def distance(a,b): return math.hypot(a[0]-b[0],a[1]-b[1])

# -------- CLASSES --------
class Player:
    def __init__(self,x,y,color,name):
        self.pos=[x,y]; self.radius=20; self.keys_collected=0
        self.alive=True; self.health=PLAYER_MAX_HEALTH
        self.color=color; self.name=name; self.bullets=[]
        self.face_timer=0
    def move(self,dx,dy,dt):
        if dx!=0 and dy!=0: dx*=0.7071; dy*=0.7071
        self.pos[0]=clamp(self.pos[0]+dx*PLAYER_SPEED*dt*0.06,20,WORLD_WIDTH-20)
        self.pos[1]=clamp(self.pos[1]+dy*PLAYER_SPEED*dt*0.06,20,WORLD_HEIGHT-20)
    def draw(self,screen,scale,offset):
        sx,sy=int(self.pos[0]*scale+offset[0]), int(self.pos[1]*scale+offset[1])
        pygame.draw.rect(screen,self.color,(sx-8,sy-15,16,25))
        face_color = WHITE if self.face_timer <= 0 else GOLD
        pygame.draw.circle(screen,face_color,(sx,sy-20),6)
        self.face_timer = max(0, self.face_timer-1)
    def hit(self):
        self.health -= 1
        self.face_timer = 20
        if self.health <= 0:
            self.alive = False

class Bullet:
    def __init__(self,x,y,target):
        self.pos=[x,y]; self.target=target; self.speed=20; self.radius=5; self.active=True
        dx,dy=target[0]-x,target[1]-y; dist=math.hypot(dx,dy)+1e-6
        self.dir=[dx/dist, dy/dist]
    def update(self): 
        self.pos[0]+=self.dir[0]*self.speed; self.pos[1]+=self.dir[1]*self.speed
        if not (0<self.pos[0]<WORLD_WIDTH and 0<self.pos[1]<WORLD_HEIGHT): self.active=False
    def draw(self,screen,scale,offset):
        if self.active:
            sx,sy=int(self.pos[0]*scale+offset[0]),int(self.pos[1]*scale+offset[1])
            pygame.draw.circle(screen,BULLET_COLOR,(sx,sy),max(2,int(self.radius*scale)))

class Snake:
    def __init__(self,x,y):
        self.pos=[x,y]; self.radius=22; self.speed=SNAKE_SPEED
    def update(self,target,dt):
        vx,vy=target[0]-self.pos[0], target[1]-self.pos[1]
        dist=math.hypot(vx,vy)+1e-6
        vx/=dist; vy/=dist
        self.pos[0]+=vx*self.speed*dt*0.06; self.pos[1]+=vy*self.speed*dt*0.06
    def draw(self,screen,scale,offset):
        sx,sy=int(self.pos[0]*scale+offset[0]),int(self.pos[1]*scale+offset[1])
        pygame.draw.circle(screen,DARKRED,(sx,sy),max(2,int(self.radius*scale)))

class Boss:
    def __init__(self,x,y):
        self.pos=[x,y]; self.radius=35; self.speed=2.2; self.alive=True
        self.health=8; self.bullets=[]; self.cooldown=0
    def update(self,player_pos,dt):
        if not self.alive: return
        vx,vy=player_pos[0]-self.pos[0], player_pos[1]-self.pos[1]
        dist=math.hypot(vx,vy)+1e-6
        vx/=dist; vy/=dist
        self.pos[0]+=vx*self.speed*dt*0.06; self.pos[1]+=vy*self.speed*dt*0.06
    def shoot(self,player_pos):
        if self.cooldown<=0:
            self.bullets.append(Bullet(self.pos[0],self.pos[1],player_pos))
            self.cooldown=60
        else:
            self.cooldown-=1
    def draw(self,screen,scale,offset):
        if not self.alive: return
        sx,sy=int(self.pos[0]*scale+offset[0]),int(self.pos[1]*scale+offset[1])
        pygame.draw.circle(screen,(80,0,80),(sx,sy),max(2,int(self.radius*scale)))
        for b in self.bullets: b.draw(screen,scale,offset)

class PuzzleStation:
    def __init__(self,x,y,question,answer):
        self.pos=(x,y); self.radius=26; self.question=question; self.answer=answer; self.solved=False
    def near(self,player_pos): return distance(self.pos,player_pos)<120
    def draw(self,screen,font,scale,offset,tick):
        sx,sy=int(self.pos[0]*scale+offset[0]),int(self.pos[1]*scale+offset[1])
        glow=int(3+math.sin(tick*0.1)*3)
        color=RED if not self.solved else GOLD
        pygame.draw.circle(screen,color,(sx,sy),max(2,int((self.radius+glow)*scale)),max(2,int(2*scale)))
        pygame.draw.circle(screen,DARKGRAY,(sx,sy),max(2,int(self.radius*scale)))
        qtxt=font.render("?",True,WHITE if not self.solved else BLACK)
        screen.blit(qtxt,(sx-qtxt.get_width()//2,sy-qtxt.get_height()//2))

# IQ Question Interface
def iq_question_game(screen,clock,font,question,answer):
    input_text=""; messages=[]
    while True:
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            if ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_ESCAPE: return False
                if ev.key==pygame.K_BACKSPACE: input_text=input_text[:-1]
                elif ev.key==pygame.K_RETURN:
                    if input_text.strip().lower()==answer.lower(): return True
                    else: messages.append("Wrong answer!"); input_text=""
                else:
                    if ev.unicode.isprintable() and len(input_text)<60: input_text+=ev.unicode
        screen.fill((20,10,10))
        title=font.render("IQ Question - Solve to get the key",True,GOLD)
        screen.blit(title,((SCREEN_WIDTH-title.get_width())//2,40))
        qline=font.render(question,True,WHITE)
        screen.blit(qline,((SCREEN_WIDTH-qline.get_width())//2,120))
        ansline=font.render("Answer: "+input_text,True,TEAL)
        screen.blit(ansline,((SCREEN_WIDTH-ansline.get_width())//2,200))
        yy=240
        for m in messages[-3:]:
            screen.blit(font.render(m,True,RED),((SCREEN_WIDTH-font.size(m)[0])//2,yy)); yy+=24
        pygame.display.flip(); clock.tick(FPS)

# Shooting
def handle_shooting(player,mouse_pos):
    player.bullets.append(Bullet(player.pos[0],player.pos[1],mouse_pos))

def update_bullets(player,snakes,boss=None):
    for bullet in player.bullets:
        if not bullet.active: continue
        bullet.update()
        for snake in snakes[:]:
            if distance(bullet.pos,snake.pos)<25:
                snakes.remove(snake); bullet.active=False; break
        if boss and boss.alive and distance(bullet.pos,boss.pos)<40:
            boss.health-=1; bullet.active=False
            if boss.health<=0: boss.alive=False

# Static city
def render_static_city():
    surface=pygame.Surface((WORLD_WIDTH,WORLD_HEIGHT))
    surface.fill(SKY_BOTTOM)
    for y in range(0,WORLD_HEIGHT,200):
        pygame.draw.rect(surface,ROAD,(0,y,WORLD_WIDTH,80))
        for x in range(0,WORLD_WIDTH,60):
            pygame.draw.rect(surface,ROAD_LINES,(x,y+38,40,4))
    for i in range(40):
        tx,ty=random.randint(0,WORLD_WIDTH),random.randint(0,WORLD_HEIGHT)
        pygame.draw.rect(surface,TREE,(tx,ty,12,24))
    return surface.convert()

# Character menu
def character_menu(screen,clock,font):
    avatars=[]
    for i,name in enumerate(CHARACTERS):
        surf=pygame.Surface((60,80),pygame.SRCALPHA)
        pygame.draw.rect(surf,CHAR_COLORS[i],(20,20,20,40))
        pygame.draw.circle(surf,WHITE,(30,15),12)
        pygame.draw.circle(surf,BLACK,(24,12),3)
        pygame.draw.circle(surf,BLACK,(36,12),3)
        pygame.draw.line(surf,BLACK,(24,22),(36,22),2)
        avatars.append(surf)
    selected=None
    while selected is None:
        screen.fill(DARKGRAY)
        title = font.render("Select Your Character", True, GOLD)
        screen.blit(title,((SCREEN_WIDTH-title.get_width())//2,50))
        mx,my=pygame.mouse.get_pos()
        for i,name in enumerate(CHARACTERS):
            x=150+i*200; y=300
            rect=pygame.Rect(x-30,y-40,60,80)
            if rect.collidepoint((mx,my)):
                pygame.draw.rect(screen,LIGHTGRAY,rect.inflate(10,10),border_radius=8)
                if pygame.mouse.get_pressed()[0]:
                    selected=(name,CHAR_COLORS[i])
                    return selected
            screen.blit(avatars[i],(x-30,y-40))
            name_text=pygame.font.SysFont("arial",16).render(name,True,WHITE)
            screen.blit(name_text,(x-name_text.get_width()//2,y+45))
        pygame.display.flip(); clock.tick(FPS)

# Cinematic boss fight
def cinematic_boss_fight(screen,font,player,boss,scale,offset,clock):
    flash_time=0
    while boss.alive and player.alive:
        dt=clock.tick(FPS)
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            if ev.type==pygame.MOUSEBUTTONDOWN: handle_shooting(player,pygame.mouse.get_pos())
        keys=pygame.key.get_pressed()
        dx=keys[pygame.K_RIGHT]-keys[pygame.K_LEFT]
        dy=keys[pygame.K_DOWN]-keys[pygame.K_UP]
        player.move(dx,dy,dt)
        boss.update(player.pos,dt); boss.shoot(player.pos)
        update_bullets(player,[],boss)
        for b in boss.bullets:
            b.update()
            if distance(b.pos,player.pos)<30:
                player.hit(); b.active=False
        boss.bullets=[b for b in boss.bullets if b.active]
        screen.fill(DARKGRAY)
        flash_time+=1
        color=(255,0,0) if (flash_time//10)%2==0 else (100,0,150)
        pygame.draw.circle(screen,color,(int(boss.pos[0]*scale+offset[0]),int(boss.pos[1]*scale+offset[1])),int(boss.radius*scale))
        for b in player.bullets: b.draw(screen,scale,offset)
        for b in boss.bullets: b.draw(screen,scale,offset)
        player.draw(screen,scale,offset)
        hud=font.render(f"HP: {player.health} | Kai HP: {boss.health}",True,GOLD)
        screen.blit(hud,(20,20))
        pygame.display.flip()
    screen.fill(BLACK)
    if boss.alive==False:
        victory=font.render(f"{player.name} defeated Kai Parker! You Win!",True,GOLD)
        screen.blit(victory,((SCREEN_WIDTH-victory.get_width())//2,SCREEN_HEIGHT//2))
    else:
        defeat=font.render(f"{player.name} was defeated! Game Over!",True,RED)
        screen.blit(defeat,((SCREEN_WIDTH-defeat.get_width())//2,SCREEN_HEIGHT//2))
    pygame.display.flip()
    pygame.time.wait(4000)
    pygame.quit(); sys.exit()

# -------------------- MAIN --------------------
def main():
    pygame.init()
    screen=pygame.display.set_mode((SCREEN_WIDTH,SCREEN_HEIGHT))
    pygame.display.set_caption("Escape the Python - Cinematic Edition")
    clock=pygame.time.Clock()
    font=pygame.font.SysFont("arial",24)

    # Character select
    name,color=character_menu(screen,clock,font)
    player=Player(400,400,color,name)

    # City and setup
    city_surf=render_static_city()
    puzzles=[PuzzleStation(random.randint(100,WORLD_WIDTH-100),random.randint(100,WORLD_HEIGHT-100),f"Q{i+1}: Type 'answer' to continue","answer") for i in range(NUM_KEYS)]
    snakes=[Snake(random.randint(0,WORLD_WIDTH),random.randint(0,WORLD_HEIGHT)) for _ in range(3)]
    boss=Boss(WORLD_WIDTH-400,WORLD_HEIGHT-400)

    tick=0; scale=0.4
    while True:
        dt=clock.tick(FPS)
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            if ev.type==pygame.MOUSEBUTTONDOWN: handle_shooting(player,pygame.mouse.get_pos())
        keys=pygame.key.get_pressed()
        dx=keys[pygame.K_RIGHT]-keys[pygame.K_LEFT]
        dy=keys[pygame.K_DOWN]-keys[pygame.K_UP]
        player.move(dx,dy,dt)
        for s in snakes: s.update(player.pos,dt)
        update_bullets(player,snakes,boss)
        for p in puzzles:
            if p.near(player.pos) and not p.solved:
                solved=iq_question_game(screen,clock,font,p.question,p.answer)
                if solved:
                    p.solved=True; player.keys_collected+=1
                    snakes.append(Snake(random.randint(0,WORLD_WIDTH),random.randint(0,WORLD_HEIGHT)))
        offset=[SCREEN_WIDTH//2-player.pos[0]*scale,SCREEN_HEIGHT//2-player.pos[1]*scale]
        screen.fill(BLACK)
        scaled_city=pygame.transform.smoothscale(city_surf,(int(WORLD_WIDTH*scale),int(WORLD_HEIGHT*scale)))
        screen.blit(scaled_city,(offset[0],offset[1]))
        for p in puzzles: p.draw(screen,font,scale,offset,tick)
        for s in snakes: s.draw(screen,scale,offset)
        for b in player.bullets: b.draw(screen,scale,offset)
        player.draw(screen,scale,offset)
        hud=font.render(f"Keys: {player.keys_collected}/{NUM_KEYS}  Snakes: {len(snakes)}  HP: {player.health}",True,GOLD)
        screen.blit(hud,(20,20))

        # Start cinematic boss fight
        if player.keys_collected>=NUM_KEYS:
            cinematic_boss_fight(screen,font,player,boss,scale,offset,clock)

        if not player.alive:
            screen.fill(BLACK)
            defeat=font.render(f"{player.name} was defeated! Game Over!",True,RED)
            screen.blit(defeat,((SCREEN_WIDTH-defeat.get_width())//2,SCREEN_HEIGHT//2))
            pygame.display.flip()
            pygame.time.wait(4000)
            pygame.quit(); sys.exit()

        pygame.display.flip()
        tick+=1

if __name__=="__main__":
    main()
