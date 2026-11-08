"""Digital acceptance. Run with the project Python; no printer required."""
import io
import json
import tempfile
import zipfile
from itertools import combinations
from pathlib import Path
import cadquery as cq
import trimesh
from model import *
from outputs import archive, drawing

def volume(a,b):
    return a.intersect(b).Volume()

def verify_case(raw):
    p=settings(raw)
    parts=build(p)
    by={part.id:part.shape for part in parts}
    for part in parts:
        assert part.shape.isValid(),(p,part.id)
        if printable(part):
            assert len(part.shape.Solids())==1 and part.shape.Volume()>1,(p,part.id)
    for a,b in combinations(parts,2):
        v=volume(a.shape,b.shape)
        assert v<.001,(raw,a.id,b.id,"rest",v)
    if p["mode"]=="panel":
        # Moving key clears housing throughout stroke, then meets the stop.
        for stroke in (0.2,0.5,0.949):
            assert volume(by["key"].translate((0,0,-stroke)),by["housing"])<.001,(raw,stroke)
            assert volume(by["key"].translate((0,0,-stroke)),by["insert"])<.001
        assert volume(by["key"].translate((0,0,-.99)),by["insert"])>.001
        for depth in (1,2,4,6,8,10,12,14,18):
            assert volume(by["key"].translate((0,0,-depth)),by["housing"])<.001,(raw,"key insertion",depth)
        for depth in (1,3,6,10,15):
            assert volume(by["insert"].translate((0,0,-depth)),by["housing"])<.001,(raw,"insert assembly",depth)
        # Switch and leads can be fed from the side, before the insert goes into the cup.
        for off in (1,3,5,9,15):
            for name in ("switch","stem","leads"):
                assert volume(by[name].translate((off,0,0)),by["insert"])<.001,(raw,name,"slide",off)
    else:
        first,travel=limit_dimensions(p)
        sign=1 if p["hand"]=="right" else -1
        def move(stroke):
            angle=math.degrees(math.asin(stroke/p["arm"]))*sign
            return by["lever"].rotate((0,0,14),(0,1,14),angle)
        for stroke in (.2,first,travel-.04):
            for name in ("base","switch","pin"):
                assert volume(move(stroke),by[name])<.001,(raw,name,stroke)
        assert volume(move(travel+.08),by["base"])>.001,(raw,"missed stop")
    print("CAD OK",raw)

def verify_zip(raw,path=None):
    p=settings(raw)
    blob=archive(p)
    with zipfile.ZipFile(io.BytesIO(blob)) as z, tempfile.TemporaryDirectory() as td:
        assert json.loads(z.read("parameters.json"))==p
        for name in z.namelist():
            if name.endswith(".stl"):
                mesh=trimesh.load(io.BytesIO(z.read(name)),file_type="stl")
                assert mesh.is_volume and len(mesh.split())==1 and mesh.bounds[0,2]>-.001,name
        stp=Path(td)/"test.step"
        stp.write_bytes(z.read("assembly.step"))
        assert len(cq.importers.importStep(str(stp)).solids().vals())>=6
        assert 'width="110mm"' in z.read("mounting.svg").decode()
    if path:
        path.parent.mkdir(exist_ok=True);path.write_bytes(blob)
    print("STL / STEP / SVG OK",p["mode"],len(blob))

if __name__=="__main__":
    for raw in [{},{"mode":"limit"},{"hole":20,"key":12,"panel":1,"light":"key","trim":-.15,"gap":.15},
                {"hole":34,"key":24,"panel":5,"light":"indicator","material":"sla","moving":"sla","trim":.15,"gap":.45},
                {"hole":34,"key":12,"panel":1,"gap":.15,"convention":"diameter"},
                {"mode":"limit","arm":20,"pitch":19,"slot":4,"extra":1.5,"trim":.15,"material":"sla","moving":"sla"},
                {"mode":"limit","arm":40,"pitch":34,"slot":12,"extra":.5,"trim":-.15,"hand":"left","gap":.45},
                {"mode":"limit","arm":20,"extra":1.5,"gap":.15,"convention":"diameter"}]:
        verify_case(raw)
    for raw in [{"hole":20,"key":16},{"gap":float("nan")},{"mode":"other"}]:
        try:settings(raw)
        except ValueError:continue
        raise AssertionError(raw)
    root=Path(__file__).resolve().parent/"kits"
    verify_zip({},root/"Tact-panel-D22.zip")
    verify_zip({"mode":"limit"},root/"Tact-limit-L24.zip")
    verify_zip({"light":"key","material":"sla","moving":"sla","hole":20,"key":12})
    verify_zip({"light":"indicator","hole":34,"key":24})
    print("Passed")
