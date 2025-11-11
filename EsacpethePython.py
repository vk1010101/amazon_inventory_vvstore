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
DARKGRAY=(28,28,40); LIGHTGRAY=(150,150,150)
GREEN=(60,180,80); SKY_BOTTOM=(18,18,32)
TEAL=(20,150,160)
BULLET_COLOR=(255,255,0)

NEON_BLUE=(80,160,255)
NEON_PINK=(255,90,200)
NEON_CYAN=(80,255,240)
NEON_PURPLE=(140,90,255)
NEON_AMBER=(255,170,60)

GRID_COLOR=(35,45,80)
HORIZON_GLOW=(90,20,120)

# Characters (only 5 now)
CHARACTERS=["Stefan","Damon","Elena","Vanshul","Caroline"]
CHAR_COLORS=[(200,0,0),(0,200,0),(0,0,200),(200,200,0),(200,0,200)]

# -------- GFX HELPERS --------
def make_vignette(size):
    surface=pygame.Surface(size,pygame.SRCALPHA)
    cx,cy=size[0]/2,size[1]/2
    max_dist=math.hypot(cx,cy)
    for y in range(size[1]):
        for x in range(size[0]):
            dist=math.hypot(x-cx,y-cy)
            alpha=int(clamp((dist/max_dist-0.55)*255*1.2,0,180))
            surface.set_at((x,y),(10,0,30,alpha))
    return surface

def make_scanlines(size):
    surf=pygame.Surface(size,pygame.SRCALPHA)
    for y in range(0,size[1],3):
        pygame.draw.line(surf,(0,0,0,40),(0,y),(size[0],y))
    return surf

# -------- UTILITIES --------
def clamp(v,a,b): return max(a,min(b,v))
def distance(a,b): return math.hypot(a[0]-b[0],a[1]-b[1])

# -------- CLASSES --------
class Particle:
    def __init__(self,pos,vel,color,life,size):
        self.pos=list(pos)
        self.vel=list(vel)
        self.color=color
        self.life=life
        self.size=size

    def update(self):
        self.pos[0]+=self.vel[0]
        self.pos[1]+=self.vel[1]
        self.life-=1
        return self.life>0

    def draw(self,screen,scale,offset):
        if self.life<=0:
            return
        alpha=int(clamp(self.life*8,40,255))
        color=(*self.color,alpha)
        surf=pygame.Surface((self.size*2,self.size*2),pygame.SRCALPHA)
        pygame.draw.circle(surf,color,(self.size,self.size),self.size)
        sx=int(self.pos[0]*scale+offset[0])-self.size
        sy=int(self.pos[1]*scale+offset[1])-self.size
        screen.blit(surf,(sx,sy),special_flags=pygame.BLEND_ADD)

class ParticleSystem:
    def __init__(self):
        self.particles=[]

    def emit(self,pos,amount,color_range=(NEON_CYAN,NEON_PINK)):
        for _ in range(amount):
            angle=random.uniform(0,math.tau)
            speed=random.uniform(1,4)
            vel=(math.cos(angle)*speed,math.sin(angle)*speed)
            life=random.randint(15,35)
            size=random.randint(3,6)
            color=random.choice(color_range)
            self.particles.append(Particle(pos,vel,color,life,size))

    def update(self):
        self.particles=[p for p in self.particles if p.update()]

    def draw(self,screen,scale,offset):
        for p in self.particles:
            p.draw(screen,scale,offset)

class Player:
    def __init__(self,x,y,color,name):
        self.pos=[x,y]; self.radius=20; self.keys_collected=0
        self.alive=True; self.health=PLAYER_MAX_HEALTH
        self.color=color; self.name=name; self.bullets=[]
        self.face_timer=0
        self.trail=ParticleSystem()
        self.muzzle=ParticleSystem()
    def move(self,dx,dy,dt):
        if dx!=0 and dy!=0: dx*=0.7071; dy*=0.7071
        self.pos[0]=clamp(self.pos[0]+dx*PLAYER_SPEED*dt*0.06,20,WORLD_WIDTH-20)
        self.pos[1]=clamp(self.pos[1]+dy*PLAYER_SPEED*dt*0.06,20,WORLD_HEIGHT-20)
        if dx or dy:
            self.trail.emit((self.pos[0],self.pos[1]+30),3,(NEON_BLUE,NEON_PURPLE,NEON_CYAN))
    def draw(self,screen,scale,offset):
        sx,sy=int(self.pos[0]*scale+offset[0]), int(self.pos[1]*scale+offset[1])
        glow=pygame.Surface((70,70),pygame.SRCALPHA)
        pygame.draw.circle(glow,(*NEON_CYAN,40),(35,35),28)
        pygame.draw.circle(glow,(*NEON_PURPLE,120),(35,35),20)
        screen.blit(glow,(sx-35,sy-35),special_flags=pygame.BLEND_ADD)
        pygame.draw.rect(screen,self.color,(sx-10,sy-18,20,32),border_radius=6)
        pygame.draw.rect(screen,WHITE,(sx-10,sy-8,20,4),border_radius=2)
        face_color = WHITE if self.face_timer <= 0 else GOLD
        pygame.draw.circle(screen,face_color,(sx,sy-20),7)
        pygame.draw.circle(screen,BLACK,(sx-3,sy-21),2)
        pygame.draw.circle(screen,BLACK,(sx+3,sy-21),2)
        pygame.draw.line(screen,WHITE,(sx-4,sy-16),(sx+4,sy-16),2)
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
            radius=max(2,int(self.radius*scale))
            glow=pygame.Surface((radius*4,radius*4),pygame.SRCALPHA)
            pygame.draw.circle(glow,(*NEON_AMBER,160),(radius*2,radius*2),radius*2)
            pygame.draw.circle(glow,(*NEON_CYAN,220),(radius*2,radius*2),radius)
            screen.blit(glow,(sx-radius*2,sy-radius*2),special_flags=pygame.BLEND_ADD)

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
        radius=max(6,int(self.radius*scale))
        body=pygame.Surface((radius*2,radius*2),pygame.SRCALPHA)
        pygame.draw.circle(body,(*NEON_PINK,140),(radius,radius),radius)
        pygame.draw.circle(body,(*NEON_PURPLE,220),(radius,radius),radius-4)
        pygame.draw.circle(body,WHITE,(radius-4,radius-4),3)
        pygame.draw.circle(body,WHITE,(radius+4,radius-4),3)
        screen.blit(body,(sx-radius,sy-radius),special_flags=pygame.BLEND_ADD)

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
        radius=max(10,int(self.radius*scale))
        aura=pygame.Surface((radius*4,radius*4),pygame.SRCALPHA)
        pygame.draw.circle(aura,(*NEON_PURPLE,60),(radius*2,radius*2),radius*2)
        pygame.draw.circle(aura,(*NEON_PINK,120),(radius*2,radius*2),radius+6)
        pygame.draw.circle(aura,(*NEON_CYAN,240),(radius*2,radius*2),radius)
        screen.blit(aura,(sx-radius*2,sy-radius*2),special_flags=pygame.BLEND_ADD)
        pygame.draw.circle(screen,WHITE,(sx,sy),3)
        for b in self.bullets: b.draw(screen,scale,offset)

class PuzzleStation:
    def __init__(self,x,y,question,answer):
        self.pos=(x,y); self.radius=26; self.question=question; self.answer=answer; self.solved=False
    def near(self,player_pos): return distance(self.pos,player_pos)<120
    def draw(self,screen,font,scale,offset,tick):
        sx,sy=int(self.pos[0]*scale+offset[0]),int(self.pos[1]*scale+offset[1])
        glow=int(6+math.sin(tick*0.12)*6)
        base_color=NEON_PINK if not self.solved else NEON_CYAN
        aura=pygame.Surface((120,120),pygame.SRCALPHA)
        pygame.draw.circle(aura,(*base_color,90),(60,60),40+glow)
        pygame.draw.circle(aura,(*NEON_PURPLE,120),(60,60),28)
        screen.blit(aura,(sx-60,sy-60),special_flags=pygame.BLEND_ADD)
        pygame.draw.circle(screen,WHITE,(sx,sy),max(4,int(self.radius*scale)),2)
        qtxt=font.render("?",True,WHITE if not self.solved else GOLD)
        screen.blit(qtxt,(sx-qtxt.get_width()//2,sy-qtxt.get_height()//2))

# IQ Question Interface
def iq_question_game(screen,clock,font,question,answer):
    input_text=""; messages=[]
    vignette=make_vignette((SCREEN_WIDTH,SCREEN_HEIGHT))
    scanlines=make_scanlines((SCREEN_WIDTH,SCREEN_HEIGHT))
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
        backdrop=pygame.Surface((SCREEN_WIDTH,SCREEN_HEIGHT))
        for y in range(SCREEN_HEIGHT):
            t=y/SCREEN_HEIGHT
            color=(int(18+120*t),int(12+80*(1-t)),int(40+90*t))
            pygame.draw.line(backdrop,color,(0,y),(SCREEN_WIDTH,y))
        screen.blit(backdrop,(0,0))
        panel=pygame.Surface((SCREEN_WIDTH-200,SCREEN_HEIGHT-240),pygame.SRCALPHA)
        pygame.draw.rect(panel,(20,20,40,200),panel.get_rect(),border_radius=24)
        pygame.draw.rect(panel,(NEON_CYAN[0],NEON_CYAN[1],NEON_CYAN[2],120),panel.get_rect(),4,24)
        screen.blit(panel,(100,120))
        title=font.render("Decrypt the Serpent",True,NEON_PINK)
        screen.blit(title,((SCREEN_WIDTH-title.get_width())//2,150))
        qline=font.render(question,True,WHITE)
        screen.blit(qline,((SCREEN_WIDTH-qline.get_width())//2,220))
        ansline=font.render("Answer: "+input_text,True,NEON_CYAN)
        screen.blit(ansline,((SCREEN_WIDTH-ansline.get_width())//2,280))
        yy=320
        for m in messages[-3:]:
            warn=font.render(m,True,NEON_AMBER)
            screen.blit(warn,((SCREEN_WIDTH-warn.get_width())//2,yy)); yy+=28
        tip=font.render("Press Enter to submit · Esc to bail",True,WHITE)
        screen.blit(tip,((SCREEN_WIDTH-tip.get_width())//2,SCREEN_HEIGHT-160))
        screen.blit(vignette,(0,0),special_flags=pygame.BLEND_MULT)
        screen.blit(scanlines,(0,0),special_flags=pygame.BLEND_SUB)
        pygame.display.flip(); clock.tick(FPS)

# Shooting
def handle_shooting(player,mouse_pos):
    player.bullets.append(Bullet(player.pos[0],player.pos[1],mouse_pos))
    player.muzzle.emit((player.pos[0],player.pos[1]-10),8,(NEON_AMBER,NEON_PINK,NEON_CYAN))

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

# Static world reimagined
def render_neon_world():
    surface=pygame.Surface((WORLD_WIDTH,WORLD_HEIGHT))
    gradient=pygame.Surface((WORLD_WIDTH,WORLD_HEIGHT))
    for y in range(WORLD_HEIGHT):
        t=y/WORLD_HEIGHT
        r=int((1-t)*HORIZON_GLOW[0]+t*SKY_BOTTOM[0])
        g=int((1-t)*HORIZON_GLOW[1]+t*SKY_BOTTOM[1])
        b=int((1-t)*HORIZON_GLOW[2]+t*SKY_BOTTOM[2])
        pygame.draw.line(gradient,(r,g,b),(0,y),(WORLD_WIDTH,y))
    surface.blit(gradient,(0,0))
    for x in range(0,WORLD_WIDTH,80):
        for y in range(0,WORLD_HEIGHT,120):
            width=random.randint(80,160)
            height=random.randint(160,360)
            rect=pygame.Rect(x+random.randint(-40,40),y, width, height)
            color=(random.randint(30,70),random.randint(30,70),random.randint(70,140))
            pygame.draw.rect(surface,color,rect)
            for w in range(rect.y,rect.y+rect.height,25):
                if random.random()<0.7:
                    pygame.draw.line(surface,(NEON_BLUE[0],NEON_BLUE[1],NEON_BLUE[2]),(rect.x,w),(rect.x+rect.width,w),2)
    grid=pygame.Surface((WORLD_WIDTH,WORLD_HEIGHT),pygame.SRCALPHA)
    for y in range(0,WORLD_HEIGHT,60):
        alpha=int(clamp(255-(y/WORLD_HEIGHT)*255,40,180))
        pygame.draw.line(grid,(NEON_BLUE[0],NEON_BLUE[1],NEON_BLUE[2],alpha),(0,y),(WORLD_WIDTH,y),1)
    for x in range(0,WORLD_WIDTH,60):
        pygame.draw.line(grid,(GRID_COLOR[0],GRID_COLOR[1],GRID_COLOR[2],90),(x,0),(x,WORLD_HEIGHT),1)
    surface.blit(grid,(0,0))
    return surface.convert()

# Character menu
def character_menu(screen,clock,font):
    avatars=[]
    for i,name in enumerate(CHARACTERS):
        surf=pygame.Surface((60,80),pygame.SRCALPHA)
        pygame.draw.rect(surf,CHAR_COLORS[i],(18,26,24,40),border_radius=8)
        pygame.draw.rect(surf,WHITE,(20,38,20,4),border_radius=2)
        pygame.draw.circle(surf,WHITE,(30,20),12)
        pygame.draw.circle(surf,BLACK,(26,18),3)
        pygame.draw.circle(surf,BLACK,(34,18),3)
        pygame.draw.arc(surf,BLACK,(22,24,16,10),math.pi*0.1,math.pi-0.1,2)
        avatars.append(surf)
    selected=None
    while selected is None:
        screen.fill(BLACK)
        gradient=pygame.Surface((SCREEN_WIDTH,SCREEN_HEIGHT))
        for y in range(SCREEN_HEIGHT):
            t=y/SCREEN_HEIGHT
            color=(int(20+120*(1-t)),int(10+40*t),int(40+140*t))
            pygame.draw.line(gradient,color,(0,y),(SCREEN_WIDTH,y))
        screen.blit(gradient,(0,0))
        title = font.render("Assemble Your Legend", True, NEON_CYAN)
        screen.blit(title,((SCREEN_WIDTH-title.get_width())//2,60))
        mx,my=pygame.mouse.get_pos()
        for i,name in enumerate(CHARACTERS):
            x=150+i*200; y=300
            rect=pygame.Rect(x-30,y-40,60,80)
            if rect.collidepoint((mx,my)):
                pygame.draw.rect(screen,NEON_PINK,rect.inflate(16,16),4,border_radius=16)
                if pygame.mouse.get_pressed()[0]:
                    selected=(name,CHAR_COLORS[i])
                    return selected
            glow=pygame.Surface((120,140),pygame.SRCALPHA)
            pygame.draw.ellipse(glow,(*NEON_PURPLE,60),(0,40,120,60))
            screen.blit(glow,(x-60,y-40),special_flags=pygame.BLEND_ADD)
            screen.blit(avatars[i],(x-30,y-40))
            name_text=pygame.font.SysFont("arial",20,bold=True).render(name,True,WHITE)
            screen.blit(name_text,(x-name_text.get_width()//2,y+45))
        tip=pygame.font.SysFont("arial",18).render("WASD/Arrow keys to move · Click to blast",True,NEON_AMBER)
        screen.blit(tip,((SCREEN_WIDTH-tip.get_width())//2,SCREEN_HEIGHT-80))
        pygame.display.flip(); clock.tick(FPS)

# Cinematic boss fight
def cinematic_boss_fight(screen,font,player,boss,scale,offset,clock):
    flash_time=0
    vignette=make_vignette((SCREEN_WIDTH,SCREEN_HEIGHT))
    scanlines=make_scanlines((SCREEN_WIDTH,SCREEN_HEIGHT))
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
        backdrop=pygame.Surface((SCREEN_WIDTH,SCREEN_HEIGHT))
        for y in range(SCREEN_HEIGHT):
            t=y/SCREEN_HEIGHT
            color=(int(20+80*(1-t)),int(0+60*(1-t)),int(40+160*t))
            pygame.draw.line(backdrop,color,(0,y),(SCREEN_WIDTH,y))
        screen.blit(backdrop,(0,0))
        flash_time+=1
        pulses=pygame.Surface((SCREEN_WIDTH,SCREEN_HEIGHT),pygame.SRCALPHA)
        radius=180+math.sin(flash_time*0.1)*40
        pygame.draw.circle(pulses,(*NEON_AMBER,60),(SCREEN_WIDTH//2,SCREEN_HEIGHT//2),int(radius))
        screen.blit(pulses,(0,0),special_flags=pygame.BLEND_ADD)
        boss.draw(screen,scale,offset)
        for b in player.bullets: b.draw(screen,scale,offset)
        for b in boss.bullets: b.draw(screen,scale,offset)
        player.draw(screen,scale,offset)
        player.trail.update(); player.trail.draw(screen,scale,offset)
        player.muzzle.update(); player.muzzle.draw(screen,scale,offset)
        hud=font.render(f"HP: {player.health} | Kai HP: {boss.health}",True,GOLD)
        screen.blit(hud,(20,20))
        screen.blit(vignette,(0,0),special_flags=pygame.BLEND_MULT)
        screen.blit(scanlines,(0,0),special_flags=pygame.BLEND_SUB)
        pygame.display.flip()
    screen.fill(BLACK)
    if boss.alive==False:
        victory=font.render(f"{player.name} obliterated Kai Parker — fuck you , you won!",True,NEON_CYAN)
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
    city_surf=render_neon_world()
    vignette=make_vignette((SCREEN_WIDTH,SCREEN_HEIGHT))
    scanlines=make_scanlines((SCREEN_WIDTH,SCREEN_HEIGHT))
    ambient_particles=ParticleSystem()
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
                    ambient_particles.emit(p.pos,40,(NEON_CYAN,NEON_PINK,NEON_PURPLE))
                    snakes.append(Snake(random.randint(0,WORLD_WIDTH),random.randint(0,WORLD_HEIGHT)))
        offset=[SCREEN_WIDTH//2-player.pos[0]*scale,SCREEN_HEIGHT//2-player.pos[1]*scale]
        screen.fill(BLACK)
        scaled_city=pygame.transform.smoothscale(city_surf,(int(WORLD_WIDTH*scale),int(WORLD_HEIGHT*scale)))
        screen.blit(scaled_city,(offset[0],offset[1]))
        if tick%5==0:
            ambient_particles.emit((player.pos[0]+random.uniform(-120,120),player.pos[1]+random.uniform(-120,120)),1,(NEON_CYAN,NEON_PURPLE,NEON_PINK))
        ambient_particles.update(); ambient_particles.draw(screen,scale,offset)
        for p in puzzles: p.draw(screen,font,scale,offset,tick)
        for s in snakes: s.draw(screen,scale,offset)
        for b in player.bullets: b.draw(screen,scale,offset)
        player.trail.update(); player.trail.draw(screen,scale,offset)
        player.muzzle.update(); player.muzzle.draw(screen,scale,offset)
        player.draw(screen,scale,offset)
        hud=font.render(f"Keys: {player.keys_collected}/{NUM_KEYS}  Snakes: {len(snakes)}  HP: {player.health}",True,GOLD)
        screen.blit(hud,(20,20))
        screen.blit(vignette,(0,0),special_flags=pygame.BLEND_MULT)
        screen.blit(scanlines,(0,0),special_flags=pygame.BLEND_SUB)

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
