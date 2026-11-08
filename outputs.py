"""Produce previews and manufacturing files from the same B-rep solids."""
import io
import json
import tempfile
import zipfile
from pathlib import Path
import cadquery as cq
from model import build, clearance, limit_dimensions, on_bed, panel, printable, box

PALETTE=dict(body="#334856",insert="#799a9b",component="#242d35",stem="#dadcd3",metal="#a9b5bd",rubber="#8d616c",led="#f3ce77")
def pigment(p,part):
    return p["color"] if part.role=="moving" else PALETTE[part.role]

def triangles(shape):
    v,faces=shape.tessellate(0.055,0.14)
    return dict(vertices=[round(c,4) for point in v for c in point.toTuple()],
                indices=[i for tri in faces for i in tri])

def preview(p):
    half=box(0,45,-40,180,90,100)
    rows=[]
    for part in build(p):
        section=part.shape.intersect(half)
        rows.append(dict(id=part.id,name=part.name,role=part.role,spread=part.spread,
                         color=pigment(p,part),mesh=triangles(part.shape),cut=triangles(section)))
    return dict(parts=rows,settings=p)

def drawing(p):
    panel_mode=p["mode"]=="panel"
    direction=1 if p["hand"]=="right" else -1
    if panel_mode:
        r=p["hole"]/2
        profiles=f'<circle cx="0" cy="0" r="{r}"/>'
        label=f'Посадка Ø{p["hole"]:g} · панель {p["panel"]:g} мм'
        if p["light"]=="indicator":
            x=r-0.18+4.3
            profiles+=f'<circle cx="{x}" cy="0" r="2.1"/>'
            label+=f' · проход под LED Ø4,2 · оси {x:g} мм'
    else:
        width=p["slot"]+3.4
        profiles=""
        for sy in (-1,1):
            x=direction*5.5-width/2
            y=sy*p["pitch"]/2-1.7
            profiles+=f'<rect x="{x}" y="{y}" width="{width}" height="3.4" rx="1.7"/>'
        label=f'Пазы {width:g} × 3,4 · межосевое {p["pitch"]:g} мм'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="110mm" height="76mm" viewBox="-55 -38 110 76">
    <title>Такт · монтажный шаблон</title><g fill="none" stroke="#172a3c" stroke-width=".16">{profiles}</g>
    <g font-family="Arial" text-anchor="middle" fill="#172a3c"><text y="-29" font-size="3.4">Такт · монтажный шаблон 1:1</text>
    <text y="25" font-size="2.5">{label}</text><path d="M-5 29v2m0-1h10m0-1v2" stroke="#172a3c" stroke-width=".2" fill="none"/>
    <text y="34" font-size="2.3">10 мм · печать 100 %</text></g></svg>'''

def instructions(p):
    title="Панельная кнопка" if p["mode"]=="panel" else "Рычажный концевик"
    common=f"""Такт / {title}
Компонент {p['component']}, 6 × 6 × 4,3 мм, нормально разомкнутый контакт.
Расчётный зазор на сторону {clearance(p):.3f} мм. Корпус {p['material'].upper()}, подвижная деталь {p['moving'].upper()}.
STL уже повёрнуты к столу. Проверьте поддержки и свободные каналы в слайсере.
В assembly.step — печатные части, габаритная модель компонента и контактная накладка. Цвет клавиши указан в STEP.
Прозвоните две ножки: в покое цепь разомкнута, при щелчке замкнута. Подпаяйте провода до монтажа.
Накладка — мягкий силикон Ø3,3 × 1 мм; зафиксируйте её на толкателе. Жёсткость и толщину подбирают по пробному щелчку.
Схема хода показывает номинальную точку срабатывания, без моделирования упругой деформации. Проверяйте контакт мультиметром.
Монтажный SVG печатайте в масштабе 100 % и сверьте контрольный отрезок 10 мм.
"""
    if p["mode"]=="panel":
        extra=dict(none="", key="Вставьте неподвижный светодиод Ø3 мм сзади во вкладыш; подберите глубину ниже клавиши при полном нажатии, закрепите. Клавишу напечатайте полупрозрачной.",
                   indicator="Совместите отверстие в ушке ободка с отдельным отверстием Ø4,2 мм в панели. Вставьте светодиод Ø3 мм и зафиксируйте сзади.")[p["light"]]
        return common+f"""Понадобятся 2 самореза Ø2 × 6 мм для пластика, провод, малая стяжка и силиконовая накладка.
1. Напечатайте стакан, клавишу и insert.stl. Для сравнения в калибровочной папке ещё два вкладыша: ниже и выше выбранного положения на 0,15 мм.
2. Приклейте накладку к центральному выступу клавиши. Совместите две плоские грани нижнего буртика клавиши с винтовыми стойками и вложите клавишу с тыльной стороны стакана.
3. Заведите переключатель в направляющие вкладыша сбоку до упора. Пропустите выводы и проводку через окна. Закрепите оболочку провода стяжкой через два узких паза. После выбора вкладыша зафиксируйте переключатель от бокового сдвига каплей эластичного клея.
4. Установите вкладыш сзади, плавно затяните два винта. Для жёсткой смолы подберите сверло и проверьте завинчивание на пробе.
5. Защёлкните стакан в панели. Для снятия доступны язычки сзади.
{extra}
Проверьте отпускание, щелчок при нажатии у края и остановку клавиши на корпусе. При раннем поджатии выберите более низкий вкладыш.
Для защёлок используйте вязкий пластик или ударопрочную смолу; прозрачную окрашенную смолу удобно оставить для клавиши.
"""
    first,end=limit_dimensions(p)
    pin=2*(3.25+clearance(p)+(2.3 if p["material"]=="fdm" else 2.7)+0.5)
    return common+f"""Понадобятся гладкая ось Ø3 × {pin:.1f} мм, два винта М3 с шайбами, мягкая накладка. Способ фиксации оси — по месту.
1. Заведите переключатель в направляющие сбоку до упора. После выбора посадки зафиксируйте выход каплей эластичного клея и закрепите провода у основания.
2. Приклейте накладку к нижней стороне рычага, точно над штоком. Центр в 7,5 мм от оси.
3. Вставьте рычаг между ушками. Введите ось. Зафиксируйте её концы снаружи, сохранив свободное вращение.
4. Прикрепите основание к опоре через продольные пазы. Сдвигом вдоль пазов подберите место касания в механизме.
Расчёт при выбранной высоте опоры: щелчок на {first:.2f} мм хода носика, упор на {end:.2f} мм. Реальный момент зависит также от накладки и трения. Проверьте возврат в рабочей ориентации.
Используйте как сигнальный концевик. Силовой упор машины или педали нужен отдельно.
"""

def archive(p):
    parts=build(p)
    data=io.BytesIO()
    with tempfile.TemporaryDirectory() as folder, zipfile.ZipFile(data,"w",zipfile.ZIP_DEFLATED) as out:
        root=Path(folder)
        def stl(part,path):
            file=root/"print.stl"
            on_bed(part).exportStl(str(file),tolerance=0.025,angularTolerance=0.10)
            out.write(file,path)
        assembly=cq.Assembly(name="TactLab")
        for part in parts:
            if printable(part):
                if len(part.shape.Solids())!=1 or not part.shape.isValid():
                    raise ValueError("Параметры дали разрыв детали. Измените размеры.")
                stl(part,"STL/"+part.id+".stl")
            assembly.add(part.shape,name=part.id,color=cq.Color(pigment(p,part)))
        if p["mode"]=="panel":
            for delta,name in [(-0.15,"lower"),(0.15,"higher")]:
                insert=next(part for part in panel({**p,"trim":p["trim"]+delta}) if part.id=="insert")
                stl(insert,f"calibration/insert_{name}.stl")
        step=root/"assembly.step"
        assembly.export(str(step))
        out.write(step,step.name)
        out.writestr("mounting.svg",drawing(p))
        out.writestr("parameters.json",json.dumps(p,indent=2,ensure_ascii=False))
        out.writestr("Сборка.txt",instructions(p).encode("utf-8-sig"))
    return data.getvalue()
