"""Small, recognizable line drawings for the practice artist; no answer metadata.

Coordinates use the same normalized canvas and palette as student strokes. These
are deliberately sketches, not text labels, so the partner still has to guess.
"""
import copy
import math
from functools import lru_cache

INK = '#17243b'
BLUE = '#4394e7'
GREEN = '#36ad8b'
GOLD = '#ed9c40'
RED = '#e14b67'
PURPLE = '#9468d7'


def _build(word):
    out = []

    def line(*points, color=INK, width=5):
        out.append({'type': 'stroke', 'color': color, 'width': width,
                    'points': [[round(x, 4), round(y, 4)] for x, y in points]})

    def ring(x, y, rx, ry=None, color=INK, start=0, end=2*math.pi):
        ry = rx if ry is None else ry
        line(*[(x+rx*math.cos(start+(end-start)*i/32), y+ry*math.sin(start+(end-start)*i/32))
               for i in range(33)], color=color)

    def box(x, y, w, h, color=INK):
        line((x, y), (x+w, y), (x+w, y+h), (x, y+h), (x, y), color=color)

    def star(x, y, r=.2, color=GOLD):
        line(*[(x+(r if i%2 == 0 else r*.42)*math.cos(-math.pi/2+i*math.pi/5),
                y+(r if i%2 == 0 else r*.42)*math.sin(-math.pi/2+i*math.pi/5)) for i in range(11)], color=color)

    def eyes(x=.5, y=.4, gap=.09):
        ring(x-gap, y, .014)
        ring(x+gap, y, .014)

    def cloud(x=.5, y=.42, scale=1):
        pts=[(-.26,.08),(-.31,.02),(-.29,-.06),(-.21,-.09),(-.16,-.19),(-.04,-.21),(.04,-.12),(.15,-.17),(.25,-.1),(.26,-.02),(.31,.02),(.28,.1),(-.26,.08)]
        line(*[(x+a*scale, y+b*scale) for a,b in pts], color=BLUE)

    def tree():
        line((.45,.78),(.45,.5),(.35,.57),(.45,.44),(.5,.38),(.55,.5),(.55,.78), color=GOLD)
        ring(.5,.34,.23,.22,color=GREEN)
        line((.31,.79),(.69,.79),color=GREEN)

    def fish(x=.48,y=.5,color=BLUE):
        ring(x,y,.24,.13,color=color)
        line((x+.24,y),(x+.39,y-.18),(x+.39,y+.18),(x+.24,y),color=color)
        ring(x-.13,y-.03,.017)
        line((x-.08,y-.1),(x-.04,y),(x-.08,y+.1),color=color)
        line((x-.03,y-.13),(x+.08,y-.24),(x+.14,y-.11),color=color)

    def flower(x=.5,y=.4):
        line((x,y+.08),(x,y+.4),color=GREEN)
        line((x,y+.28),(x-.17,y+.17),(x-.1,y+.32),(x,y+.32),color=GREEN)
        for angle in range(0,360,60):
            a=math.radians(angle)
            ring(x+.12*math.cos(a),y+.12*math.sin(a),.095,color=RED)
        ring(x,y,.07,color=GOLD)

    def animal(kind):
        ring(.5,.63,.19,.2,color=GOLD if kind in ('sher','mushuk') else INK)
        if kind == 'sher':
            ring(.5,.35,.25,.24,color=GOLD)
        ring(.5,.36,.17,.16)
        if kind == 'quyon':
            ring(.4,.16,.055,.14)
            ring(.6,.16,.055,.14)
        elif kind in ('mushuk','sher'):
            line((.34,.32),(.3,.15),(.44,.22))
            line((.56,.22),(.7,.15),(.66,.32))
        elif kind == 'fil':
            ring(.28,.39,.12,.17)
            ring(.72,.39,.12,.17)
            line((.46,.43),(.45,.64),(.53,.69),(.63,.61),(.6,.57),(.55,.6),(.54,.43))
        eyes(.5,.34,.065)
        if kind != 'fil':
            line((.48,.42),(.52,.42),(.5,.45),(.48,.42))
            line((.5,.45),(.45,.48),(.41,.45))
            line((.5,.45),(.55,.48),(.59,.45))
        ring(.37,.81,.1,.045)
        ring(.63,.81,.1,.045)
        if kind in ('mushuk','sher'):
            line((.68,.66),(.82,.58),(.85,.4),(.79,.37),color=GOLD)
            for dy in (-.025,.025):
                line((.41,.44+dy),(.24,.42+dy))
                line((.59,.44+dy),(.76,.42+dy))

    if word == 'raketa':
        line((.38,.65),(.38,.36),(.43,.21),(.5,.1),(.57,.21),(.62,.36),(.62,.65),(.38,.65),color=BLUE)
        ring(.5,.35,.065,color=BLUE)
        line((.38,.48),(.24,.7),(.38,.66),color=RED)
        line((.62,.48),(.76,.7),(.62,.66),color=RED)
        line((.43,.67),(.4,.81),(.47,.76),(.5,.92),(.55,.77),(.6,.83),(.57,.67),color=GOLD)
        star(.18,.23,.045)
        star(.82,.4,.04)
    elif word in ('sayyora','oy','quyosh','yulduz'):
        if word == 'yulduz':
            star(.5,.48,.33)
        elif word == 'oy':
            ring(.5,.46,.3,color=BLUE)
            for x,y,r in ((.38,.3,.06),(.64,.4,.07),(.4,.59,.08),(.57,.64,.035)):
                ring(x,y,r,color=BLUE)
            star(.85,.18,.035)
        elif word == 'quyosh':
            ring(.5,.48,.2,color=GOLD)
            for i in range(12):
                a=i*math.pi/6
                line((.5+.25*math.cos(a),.48+.25*math.sin(a)),(.5+.35*math.cos(a),.48+.35*math.sin(a)),color=GOLD)
        else:
            ring(.5,.48,.23,color=PURPLE)
            ring(.5,.48,.4,.09,color=PURPLE)
            line((.34,.35),(.45,.39),(.62,.36),color=BLUE)
            star(.85,.18,.04)
    elif word == 'kitob':
        line((.5,.3),(.35,.23),(.15,.26),(.15,.74),(.35,.71),(.5,.78),(.65,.71),(.85,.74),(.85,.26),(.65,.23),(.5,.3),(.5,.78),color=BLUE)
        for y in (.38,.48,.58):
            line((.22,y),(.36,y-.01),(.44,y+.03))
            line((.56,y+.03),(.66,y-.01),(.78,y))
    elif word == 'qalam':
        line((.24,.73),(.65,.17),(.79,.27),(.38,.83),(.19,.89),(.24,.73),color=GOLD)
        line((.24,.73),(.38,.83))
        line((.3,.78),(.72,.22))
        line((.6,.24),(.74,.34),color=RED)
    elif word in ('daraxt','olma'):
        if word == 'daraxt':
            tree()
        else:
            line((.5,.3),(.36,.22),(.24,.28),(.19,.43),(.25,.65),(.38,.79),(.5,.75),(.62,.79),(.75,.65),(.81,.43),(.76,.28),(.64,.22),(.5,.3),color=RED)
            line((.5,.3),(.53,.16),color=GOLD)
            line((.53,.19),(.63,.1),(.72,.14),(.61,.22),(.53,.19),color=GREEN)
    elif word == 'kapalak':
        ring(.5,.5,.035,.24)
        for x in (.31,.69):
            ring(x,.36,.15,.21,color=PURPLE)
            ring(x,.67,.13,.15,color=RED)
        line((.48,.27),(.41,.17),(.36,.2))
        line((.52,.27),(.59,.17),(.64,.2))
    elif word in ('mushuk','sher','fil','quyon'):
        animal(word)
    elif word in ('baliq','delfin'):
        fish(color=BLUE)
        if word == 'delfin':
            line((.24,.51),(.12,.48),(.23,.45),color=BLUE)
            for y in (.76,.84):
                line((.1,y),(.25,y-.03),(.4,y),(.55,y-.03),(.7,y),(.85,y-.03),color=BLUE)
    elif word == 'qush':
        ring(.48,.49,.19,.14,color=BLUE)
        ring(.65,.36,.1,color=BLUE)
        line((.74,.34),(.87,.39),(.74,.41),color=GOLD)
        line((.3,.48),(.14,.35),(.19,.58),(.3,.54),color=BLUE)
        ring(.67,.34,.014)
        line((.41,.43),(.52,.5),(.43,.56),color=BLUE)
        for x in (.45,.56):
            line((x,.62),(x,.76),(x-.05,.79))
    elif word == 'velosiped':
        ring(.25,.65,.17)
        ring(.75,.65,.17)
        line((.25,.65),(.39,.36),(.55,.65),(.25,.65),(.61,.38),(.75,.65),color=RED)
        line((.33,.35),(.45,.35))
        line((.61,.38),(.59,.25),(.72,.25))
        ring(.55,.65,.035)
    elif word == 'samolyot':
        line((.5,.12),(.55,.2),(.56,.43),(.87,.64),(.87,.7),(.56,.59),(.56,.76),(.67,.85),(.67,.89),(.5,.84),(.33,.89),(.33,.85),(.44,.76),(.44,.59),(.13,.7),(.13,.64),(.44,.43),(.45,.2),(.5,.12),color=BLUE)
    elif word in ('kema','qayiq'):
        line((.13,.58),(.85,.58),(.73,.79),(.29,.79),(.13,.58),color=GOLD)
        line((.48,.57),(.48,.15),(.78,.51),(.51,.51),color=BLUE)
        line((.45,.22),(.23,.52),(.44,.52),color=RED)
        for x in (.13,.42,.71):
            line((x,.87),(x+.08,.83),(x+.16,.87),color=BLUE)
    elif word in ('uy','qal’a'):
        if word == 'uy':
            box(.25,.42,.5,.4,color=GOLD)
            line((.16,.43),(.5,.15),(.84,.43),(.16,.43),color=RED)
            box(.34,.51,.12,.13,color=BLUE)
            box(.56,.58,.12,.24)
        else:
            line((.14,.83),(.14,.25),(.22,.25),(.22,.34),(.3,.34),(.3,.25),(.38,.25),(.38,.45),(.62,.45),(.62,.25),(.7,.25),(.7,.34),(.78,.34),(.78,.25),(.86,.25),(.86,.83),(.14,.83),color=GOLD)
            line((.42,.83),(.42,.64),(.46,.58),(.54,.58),(.58,.64),(.58,.83))
            line((.5,.44),(.5,.12),(.69,.18),(.5,.24),color=RED)
    elif word == 'ko‘prik':
        line((.1,.43),(.9,.43),color=GOLD)
        for x in (.15,.45,.75):
            line((x,.43),(x,.72),(x+.06,.72),(x+.06,.43),color=GOLD)
        line((.1,.42),(.1,.26),(.9,.26),(.9,.42))
        for x in (.2,.35,.5,.65,.8):
            line((x,.27),(x,.43))
        line((.08,.82),(.25,.77),(.42,.82),(.6,.77),(.77,.82),(.92,.77),color=BLUE)
    elif word == 'soat':
        ring(.5,.48,.31,color=BLUE)
        for i in range(12):
            a=i*math.pi/6
            line((.5+.26*math.cos(a),.48+.26*math.sin(a)),(.5+.29*math.cos(a),.48+.29*math.sin(a)))
        line((.5,.26),(.5,.48),(.68,.56))
        ring(.5,.48,.018)
    elif word == 'ko‘zoynak':
        ring(.3,.5,.17,.14)
        ring(.7,.5,.17,.14)
        line((.47,.5),(.5,.46),(.53,.5))
        line((.13,.46),(.1,.31),(.18,.29))
        line((.87,.46),(.9,.31),(.82,.29))
    elif word == 'soyabon':
        ring(.5,.48,.34,.29,color=PURPLE,start=math.pi,end=2*math.pi)
        line((.16,.48),(.3,.43),(.43,.48),(.57,.43),(.7,.48),(.84,.48),color=PURPLE)
        line((.5,.2),(.5,.78),(.55,.84),(.62,.81),(.63,.75))
        line((.5,.2),(.4,.3),(.36,.46),color=PURPLE)
        line((.5,.2),(.6,.3),(.65,.46),color=PURPLE)
    elif word == 'poyezd':
        box(.12,.4,.4,.29,color=RED)
        box(.52,.29,.21,.4,color=BLUE)
        box(.17,.29,.09,.11)
        box(.55,.34,.13,.13)
        line((.73,.69),(.87,.69),(.8,.56),(.73,.56))
        for x in (.22,.43,.63):
            ring(x,.73,.075)
        cloud(.2,.18,.3)
        line((.08,.85),(.91,.85))
    elif word == 'toj':
        line((.23,.7),(.15,.3),(.36,.48),(.5,.19),(.64,.48),(.85,.3),(.77,.7),(.23,.7),color=GOLD)
        box(.23,.7,.54,.1,color=GOLD)
        for x,y in ((.15,.28),(.5,.17),(.85,.28)):
            ring(x,y,.03,color=RED)
        ring(.5,.58,.05,color=PURPLE)
    elif word == 'kalit':
        ring(.32,.4,.18,color=GOLD)
        ring(.32,.4,.075,color=GOLD)
        line((.46,.5),(.78,.82),(.85,.75),(.79,.69),(.74,.74),(.68,.68),(.73,.63),(.55,.45),color=GOLD)
    elif word == 'robot':
        box(.3,.2,.4,.3,color=BLUE)
        box(.33,.55,.34,.23,color=BLUE)
        eyes(.5,.31)
        line((.4,.43),(.6,.43))
        line((.5,.2),(.5,.12))
        ring(.5,.1,.025,color=RED)
        line((.33,.59),(.2,.65),(.15,.55))
        line((.67,.59),(.8,.65),(.85,.55))
        line((.4,.78),(.4,.88),(.3,.88))
        line((.6,.78),(.6,.88),(.7,.88))
    elif word == 'gitara':
        line((.54,.41),(.44,.38),(.37,.44),(.38,.54),(.27,.61),(.26,.74),(.34,.84),(.49,.86),(.6,.8),(.64,.67),(.58,.58),(.59,.48),(.54,.41),color=GOLD)
        line((.5,.6),(.65,.17),(.74,.2),(.59,.63),color=GOLD)
        box(.65,.1,.12,.13)
        ring(.46,.66,.06)
        line((.39,.78),(.52,.81))
    elif word == 'baraban':
        ring(.5,.4,.28,.09,color=RED)
        line((.22,.4),(.22,.72),(.3,.78),(.5,.81),(.7,.78),(.78,.72),(.78,.4),color=RED)
        line((.23,.45),(.34,.75),(.45,.49),(.57,.77),(.69,.47),(.77,.72),color=GOLD)
        line((.3,.12),(.6,.35))
        line((.75,.12),(.45,.35))
    elif word in ('tog‘','vulqon'):
        line((.1,.8),(.45,.2),(.55,.2),(.9,.8),(.1,.8),color=GOLD)
        if word == 'tog‘':
            line((.35,.38),(.44,.44),(.5,.33),(.59,.42),(.65,.38),color=BLUE)
        else:
            line((.45,.2),(.47,.33),(.43,.5),(.56,.63),(.54,.41),(.55,.2),color=RED)
            cloud(.5,.14,.45)
            line((.43,.16),(.32,.08),color=RED)
            line((.58,.15),(.7,.07),color=RED)
    elif word == 'kamalak':
        for r,color in ((.35,RED),(.3,GOLD),(.25,GREEN),(.2,BLUE),(.15,PURPLE)):
            ring(.5,.64,r,r,color=color,start=math.pi,end=2*math.pi)
        cloud(.17,.68,.3)
        cloud(.83,.68,.3)
    elif word in ('bulut','qor'):
        cloud(.5,.4)
        if word == 'qor':
            for x,y in ((.25,.67),(.5,.78),(.75,.66)):
                for angle in (0,math.pi/3,2*math.pi/3):
                    dx,dy=.055*math.cos(angle),.055*math.sin(angle)
                    line((x-dx,y-dy),(x+dx,y+dy),color=BLUE)
    elif word == 'gul':
        flower()
    elif word == 'toshbaqa':
        ring(.47,.5,.25,.19,color=GREEN)
        ring(.79,.45,.09,.08,color=GREEN)
        ring(.82,.42,.012)
        for x in (.32,.62):
            ring(x,.71,.07,.035,color=GREEN)
        line((.22,.5),(.12,.58),(.25,.58),color=GREEN)
        line((.36,.35),(.3,.49),(.39,.64),(.55,.64),(.64,.49),(.55,.35),(.36,.35),color=GREEN)
        line((.3,.49),(.64,.49),color=GREEN)
    elif word in ('kompyuter','telefon'):
        if word == 'telefon':
            box(.31,.12,.38,.76,color=BLUE)
            box(.34,.21,.32,.55)
            ring(.5,.82,.025)
            line((.44,.17),(.56,.17))
        else:
            box(.18,.19,.64,.43,color=BLUE)
            box(.22,.23,.56,.35)
            line((.5,.62),(.5,.75))
            line((.37,.75),(.63,.75))
            line((.22,.82),(.78,.82),(.86,.91),(.14,.91),(.22,.82))
    elif word == 'chiroq':
        ring(.5,.36,.21,.22,color=GOLD,start=math.pi*.82,end=math.pi*2.18)
        line((.32,.48),(.4,.65),(.6,.65),(.68,.48),color=GOLD)
        box(.4,.65,.2,.1)
        line((.43,.75),(.47,.8),(.53,.8),(.57,.75))
        for i in range(5):
            a=math.pi+math.pi*i/4
            line((.5+.28*math.cos(a),.36+.28*math.sin(a)),(.5+.35*math.cos(a),.36+.35*math.sin(a)),color=GOLD)
    elif word == 'yurak':
        line(*[(.5+.022*(16*math.sin(t)**3),.5-.022*(13*math.cos(t)-5*math.cos(2*t)-2*math.cos(3*t)-math.cos(4*t))) for t in [2*math.pi*i/64 for i in range(65)]],color=RED)
    elif word == 'narvon':
        line((.29,.88),(.41,.13),color=GOLD)
        line((.6,.88),(.72,.13),color=GOLD)
        for i in range(7):
            y=.2+i*.1
            x=.41-(y-.13)*.16
            line((x,y),(x+.31,y),color=GOLD)
    elif word == 'pingvin':
        ring(.5,.5,.22,.34)
        ring(.5,.58,.14,.22,color=BLUE)
        eyes(.5,.31,.065)
        line((.46,.37),(.54,.37),(.5,.42),(.46,.37),color=GOLD)
        line((.28,.44),(.15,.66),(.29,.6))
        line((.72,.44),(.85,.66),(.71,.6))
        ring(.37,.85,.095,.035,color=GOLD)
        ring(.63,.85,.095,.035,color=GOLD)
    elif word == 'ari':
        ring(.5,.52,.25,.14,color=GOLD)
        ring(.39,.29,.11,.16,color=BLUE)
        ring(.61,.29,.11,.16,color=BLUE)
        for x in (.4,.5,.6):
            line((x,.39),(x,.65))
        ring(.27,.49,.016)
        line((.75,.49),(.87,.52),(.75,.56))
        line((.28,.43),(.2,.31))
    elif word == 'muzqaymoq':
        line((.29,.46),(.5,.9),(.71,.46),(.29,.46),color=GOLD)
        ring(.5,.33,.23,.2,color=RED)
        line((.39,.63),(.61,.63),color=GOLD)
        line((.34,.52),(.56,.77),color=GOLD)
        line((.65,.52),(.44,.77),color=GOLD)
    elif word == 'shaxmat':
        box(.24,.76,.52,.1)
        line((.3,.76),(.4,.63),(.42,.36),(.35,.31),(.35,.25),(.65,.25),(.65,.31),(.58,.36),(.6,.63),(.7,.76))
        line((.5,.25),(.5,.1))
        line((.43,.16),(.57,.16))
        line((.38,.64),(.62,.64))
    elif word == 'koptok':
        ring(.5,.48,.3)
        line((.5,.32),(.65,.43),(.59,.6),(.41,.6),(.35,.43),(.5,.32))
        for a,b in (((.5,.32),(.5,.18)),((.65,.43),(.79,.4)),((.59,.6),(.68,.72)),((.41,.6),(.32,.72)),((.35,.43),(.21,.4))):
            line(a,b)
    elif word == 'raketka':
        ring(.5,.35,.2,.25,color=RED)
        line((.46,.6),(.43,.89),(.55,.89),(.54,.6),color=GOLD)
        for x in (.4,.5,.6):
            line((x,.16),(x,.54),color=BLUE)
        for y in (.25,.35,.45):
            line((.33,y),(.67,y),color=BLUE)
        ring(.8,.74,.07,color=GOLD)
    elif word == 'sumka':
        box(.23,.32,.54,.49,color=PURPLE)
        line((.36,.32),(.36,.18),(.64,.18),(.64,.32),color=PURPLE)
        box(.33,.49,.34,.2,color=RED)
        line((.5,.36),(.5,.43))
    elif word == 'stul':
        box(.3,.15,.4,.38,color=GOLD)
        line((.3,.53),(.21,.66),(.76,.66),(.7,.53),color=GOLD)
        for x in (.25,.7):
            line((x,.66),(x,.87),color=GOLD)
        line((.34,.25),(.66,.25),color=GOLD)
    elif word == 'eshik':
        box(.27,.13,.46,.75,color=GOLD)
        box(.31,.18,.38,.7,color=GOLD)
        ring(.61,.53,.025)
        box(.37,.25,.25,.2)
        box(.37,.62,.25,.17)
    elif word == 'oyna':
        box(.21,.21,.58,.58,color=BLUE)
        line((.5,.21),(.5,.79),color=BLUE)
        line((.21,.5),(.79,.5),color=BLUE)
        line((.29,.38),(.4,.27),color=BLUE)
        line((.59,.67),(.71,.55),color=BLUE)
    elif word == 'chashka':
        line((.23,.35),(.27,.75),(.36,.81),(.6,.81),(.68,.75),(.72,.35),color=GOLD)
        ring(.475,.35,.245,.065,color=GOLD)
        line((.72,.42),(.84,.4),(.9,.48),(.87,.62),(.7,.65),color=GOLD)
        for x in (.38,.52,.65):
            line((x,.24),(x-.03,.19),(x,.14),(x-.02,.08),color=BLUE)
    else:
        raise ValueError(f'No practice drawing for {word!r}')
    return out


@lru_cache(maxsize=64)
def _template(word):
    return _build(word)


def drawing_strokes(word):
    """Return fresh stroke payloads; callers may safely attach phase keys."""
    return copy.deepcopy(_template(word))
