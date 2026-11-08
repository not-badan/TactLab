"""TactLab. Millimetres, Z up. Parts are defined in their assembled coordinates."""
from dataclasses import dataclass
import math
import cadquery as cq

DEFAULT = dict(mode="panel", component="B3F-1000", hole=22, panel=2, key=14, proud=1.4,
               gap=0.30, convention="side", material="fdm", moving="fdm", light="none",
               arm=24, pitch=22, slot=6, extra=1, trim=0, hand="right", color="#ea713c")
LIMITS = dict(hole=(20,34), panel=(1,5), key=(12,24), proud=(0.6,3), gap=(0.15,0.45),
              arm=(20,40), pitch=(19,34), slot=(4,12), extra=(0.5,1.5), trim=(-0.15,0.15))
CHOICES = dict(mode=("panel","limit"), component=("B3F-1000","B3F-1002"),
               convention=("side","diameter"), material=("fdm","sla"), moving=("fdm","sla"),
               light=("none","key","indicator"), hand=("right","left"))
import re

def settings(data):
    if not isinstance(data,dict) or set(data)-set(DEFAULT):
        raise ValueError("Неизвестные параметры модели.")
    p = {**DEFAULT, **data}
    for key,(lo,hi) in LIMITS.items():
        if type(p[key]) not in (int,float) or not lo<=p[key]<=hi:
            raise ValueError(f"{key}: допустимо от {lo} до {hi} мм.")
    for key,options in CHOICES.items():
        if p[key] not in options:
            raise ValueError("Неизвестное значение поля " + key)
    if not isinstance(p["color"],str) or not re.fullmatch(r"#[0-9a-fA-F]{6}",p["color"]):
        raise ValueError("Цвет задаётся в формате #RRGGBB.")
    if p["mode"]=="panel" and p["key"]+8>p["hole"]:
        raise ValueError("Для направляющей и защёлок диаметр отверстия должен быть больше клавиши минимум на 8 мм.")
    return p

def clearance(p):
    return p["gap"] / (2 if p["convention"]=="diameter" else 1)

def box(x,y,z,dx,dy,dz):
    return cq.Solid.makeBox(dx,dy,dz,(x-dx/2,y-dy/2,z))

def cyl(x,y,z,r,h):
    return cq.Solid.makeCylinder(r,h,(x,y,z))

def axle(x,y,z,r,length):
    return cq.Solid.makeCylinder(r,length,(x,y,z),(0,1,0))

def profile_xz(points,width):
    return cq.Workplane("XZ").polyline(points).close().extrude(width/2,both=True).val()

@dataclass
class Part:
    id: str
    name: str
    shape: cq.Shape
    role: str
    spread: float = 0
    print_angle: float = 0

def cradle(x,z,base):
    # The component slides in along X. Its bent leads travel in two open channels.
    spine = box(x,0,base,10,2.4,z-base)
    rails=[]
    for side in (-1,1):
        rails.extend([box(x,side*3.77,base,9.5,1.0,z+4.18-base),
                      box(x,side*3.16,z+3.62,9.5,1.9,0.56)])
    rear=box(x-5.0,0,base,1.25,8.5,z+2.9-base)
    # Rear stop contacts central part of switch, leaving the legs free.
    stop=box(x-3.93,0,z-0.9,1.8,2.4,3.6)
    return spine.fuse(rear,stop,*rails)

def switch_parts(p,x,z,spread):
    body=box(x,0,z,6,6,3.4)
    pin=cyl(x,0,z+3.4,1.75,0.9)
    # Bent mounting leads. Nominal tip pitch 6.5 mm, widest bend 7.7 mm.
    outline=[(3,1.15),(3.42,.86),(3.85,-1.65),(3.4,-2.78),(3.4,-3.5),
             (3.1,-3.5),(3.1,-2.72),(3.54,-1.62),(3.14,.67),(3,.79)]
    leads=[profile_xz([(x+sx*u,z+v) for u,v in outline],0.7).translate((0,sy*2.25,0))
           for sx in (-1,1) for sy in (-1,1)]
    return [Part("switch",p["component"],body,"component",spread),
            Part("stem","Шток",pin,"stem",spread),
            Part("leads","Выводы (габарит)",cq.Compound.makeCompound(leads),"metal",spread)]

def panel(p):
    r=p["hole"]/2-0.18
    k=p["key"]/2
    g=clearance(p)
    wall=1.55 if p["material"]=="fdm" else 1.8
    ring=cyl(0,0,-14,r,14.05).cut(cyl(0,0,-15,r-wall,16))
    bezel=cq.Workplane(obj=cyl(0,0,0,r+2.3,1.8)).edges(">Z").chamfer(0.45).val()
    guide=cyl(0,0,-3.4,r,3.45).fuse(bezel).cut(cyl(0,0,-4,k+g,7))
    housing=ring.fuse(guide)
    for sign in (-1,1):
        housing=housing.cut(box(sign*(r+0.4),0,-12,6.2,6.0,12.05))
    yboss=r-1.83
    stop_z=-5.55
    for sign in (-1,1):
        # Separate screw bosses leave the keyed shoulder a path through the back.
        boss=cyl(0,sign*yboss,-14,1.46,7.7)
        housing=housing.fuse(boss).cut(cyl(0,sign*yboss,-14.1,0.82,6.8))
        hook=-p["panel"]-0.08
        thick=1.05 if p["material"]=="fdm" else 1.3
        outline=[(r-thick,-12.7),(r,-12.7),(r,hook-2.2),
                 (r+0.88,hook),(r-thick,hook)]
        tongue=profile_xz(outline,4.4)
        if sign<0:
            tongue=tongue.rotate((0,0,0),(0,0,1),180)
        housing=housing.fuse(tongue)
    disk=cyl(0,0,-16.3,r,2.3)
    for sy in (-1,1):
        disk=disk.cut(cyl(0,sy*yboss,-17,1.15,4))
    for sy in (-1,1):
        # Open lead channels allow a pre-wired component to slide into the saddle.
        disk=disk.cut(box((r-5.4)/2,sy*2.25,-17,r+5.8,2.25,4))
    # Holes for a small cable tie at the rear.
    for sy in (-1,1):
        disk=disk.cut(box(0,sy*5.5,-17,2.7,1.35,4))
    seat=-11.2+p["trim"]
    insert=disk.fuse(cradle(0,seat,-14.05))
    for side in (-1,1):
        insert=insert.fuse(box(-2.5,side*(k-0.7),-14.05,2,1.4,14.05+stop_z))
    shoulder=-4.6
    top=1.8+p["proud"]
    cap=cyl(0,0,-3.43,k,top+3.43).fuse(cyl(0,0,shoulder,k+0.95,1.2))
    for side in (-1,1):
        cap=cap.cut(box(0,side*(k+2.05),shoulder-0.1,2*k+4,4,1.45))
    # Bond a compliant 1 mm contact disk to the underside of the printed stud.
    pad_bottom=-11.2+4.3+0.18
    cap=cq.Workplane(obj=cap).edges(">Z").chamfer(0.45 if p["moving"]=="fdm" else 0.65).val()
    cap=cap.fuse(cyl(0,0,pad_bottom+1,1.75,shoulder-pad_bottom-1+0.05))
    parts=[]
    if p["light"]=="key":
        lx,ly=2.85,-5.15
        sleeve=cyl(lx,ly,-14.1,2.12,3.65)
        insert=insert.fuse(sleeve).cut(cyl(lx,ly,-17,1.64,12))
        insert=insert.cut(cyl(lx,ly,-16.4,1.99,3.2))
    elif p["light"]=="indicator":
        lx,ly=r+4.3,0
        bezel_ear=cyl(lx,ly,0,3.55,1.8)
        housing=housing.fuse(bezel_ear).cut(cyl(lx,ly,-0.1,1.6,2.1))
    if p["light"]!="none":
        led_z=-13.2 if p["light"]=="key" else 0
        led=cyl(lx,ly,led_z-0.55,1.88,0.55).fuse(cyl(lx,ly,led_z-0.02,1.5,2.62),
                cq.Solid.makeSphere(1.5,(lx,ly,led_z+2.6)))
        parts.append(Part("led","Светодиод Ø3 мм (габарит)",led,"led",-25 if p["light"]=="key" else -8))
    parts.extend([Part("housing","Стакан с защёлками",housing.clean(),"body",0,180),
                  Part("key","Клавиша",cap.clean(),"moving",-22,180),
                  Part("insert","Задний вкладыш",insert.clean(),"insert",-42),
                  Part("pad","Силиконовая накладка 1 мм",cyl(0,0,pad_bottom,1.65,1),"rubber",-25)])
    return parts+switch_parts(p,0,seat,-31)

def limit_dimensions(p):
    a=7.5
    first=p["arm"]*(0.18+0.25-p["trim"])/a
    return first,first+p["extra"]

def limit(p):
    length=p["arm"]
    gap=clearance(p)
    seat=6.8+p["trim"]
    pivot=14
    lever_bottom=12.28
    first,travel=limit_dimensions(p)
    angle=math.asin(travel/length)
    sx=length-3.2
    stop_top=pivot+(lever_bottom-pivot)/math.cos(angle)-sx*math.tan(angle)
    base=box((length-5)/2,0,0,length+10,13,2.8)
    for side in (-1,1):
        y=side*p["pitch"]/2
        ear=box(5.5,y/2,0,p["slot"]+7,abs(y)+6,2.8)
        slot=cq.Workplane("XY").center(5.5,y).slot2D(p["slot"]+3.4,3.4).extrude(4).val()
        base=base.fuse(ear).cut(slot)
    base=base.fuse(cradle(7.5,seat,2.75), box(sx,0,2.75,2.5,5,stop_top-2.75))
    # Narrow contact ridge gives the stop a defined X station.
    base=base.cut(box(sx-0.85,0,stop_top-0.45,1.6,5.4,1)).cut(box(sx+0.85,0,stop_top-0.45,1.6,5.4,1))
    half=3.25
    ear_width=2.3 if p["material"]=="fdm" else 2.7
    inner=half+gap
    for side in (-1,1):
        y=side*(inner+ear_width/2)
        ear=box(0,y,2.75,6.0,ear_width,pivot-2.75).fuse(axle(0,y-ear_width/2,pivot,3,ear_width))
        base=base.fuse(ear).cut(axle(0,y-ear_width/2-0.1,pivot,1.58,ear_width+0.2))
    # Tail stop establishes free position. Pin is inserted horizontally after the lever.
    base=base.fuse(box(-5.15,0,2.75,2.2,5,lever_bottom-2.75))
    thick=3.1 if p["moving"]=="fdm" else 3.45
    lever=box((length-5.9)/2,0,lever_bottom,length+5.9,2*half,thick)
    lever=lever.fuse(axle(0,-half,pivot,2.85,2*half),axle(length,-half,lever_bottom+thick/2,thick/2,2*half))
    lever=lever.cut(axle(0,-half-0.1,pivot,1.5+gap,2*half+0.2))
    for side in (-1,1):
        lever=lever.cut(box(8.5,side*3.2,lever_bottom-0.05,11.5,2.6,1.25))
    pad=cyl(7.5,0,lever_bottom-1,1.65,1)
    return [Part("base","Основание",base.clean(),"body"),
            Part("lever","Рычаг",lever.clean(),"moving",12,90),
            Part("pin","Ось Ø3 мм",axle(0,-inner-ear_width-0.5,pivot,1.5,2*(inner+ear_width+0.5)),"metal",6),
            Part("pad","Силиконовая накладка 1 мм",pad,"rubber",8)]+switch_parts(p,7.5,seat,3)

def build(p):
    parts = panel(p) if p["mode"]=="panel" else limit(p)
    if p["mode"]=="limit" and p["hand"]=="left":
        for part in parts:
            part.shape = part.shape.mirror("YZ")
    return parts

def printable(part):
    return part.role in ("body","moving","insert")

def on_bed(part):
    shape=part.shape
    if part.print_angle:
        shape=shape.rotate((0,0,0),(1,0,0),part.print_angle)
    b=shape.BoundingBox()
    return shape.translate((-(b.xmin+b.xmax)/2,-(b.ymin+b.ymax)/2,-b.zmin))
