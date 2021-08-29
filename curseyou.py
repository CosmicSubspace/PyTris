import curses
import math

'''
Thin-ish wrapper around the curses module
'''
class CurseYouEnviornment:
    def __init__(self, use_256color=False,fallback=False):
        self._stdscr=None

        self._256c=use_256color
    def __enter__(self):
        stdscr=curses.initscr()
        self._stdscr=stdscr
        curses.noecho()
        curses.cbreak()
        stdscr.keypad(True)
        curses.start_color()
        stdscr.nodelay(True)
        if curses.COLORS<256:
            self._256c=False
        return CurseYou(stdscr,use_256=self._256c)

    def __exit__(self, exc_type, exc_value, traceback):
        if self._stdscr is not None:
            self._stdscr.keypad(False)
        curses.echo()
        curses.nocbreak()
        curses.endwin()

def _rgb_f_to_1000(rgb):
    assert len(rgb)==3
    return tuple([round(f*1000) for f in rgb])
def _rgb_1000_to_f(rgb1000):
    assert len(rgb1000)==3
    return tuple([i/1000 for i in rgb1000])

def _find_closest_color(rgb1000):
    mindist=None
    candidate=0
    for c in range(curses.COLORS):
        cand1000=curses.color_content(c)
        diff=[(rgb1000[i]-cand1000[i]) for i in range(3)]
        dist=math.sqrt(sum([i*i for i in diff]))
        if (mindist is None) or (dist<mindist):
            mindist=dist
            candidate=c
    return candidate

def _256c_to_rgb(n):
    assert 16<=n<=231
    n=n-16
    b=n%6
    n=n//6
    g=n%6
    n=n//6
    r=n
    return(r/6,g/6,b/6)

def _rgb_to_256c(r,g,b):
    rn=round(r*5)
    gn=round(g*5)
    bn=round(b*5)
    res= 16 + 36*rn + 6*gn + bn
    assert 16<=res<=231
    return res

class CurseYou:
    '''
    Thin wrapper around curses module...
    '''
    def __init__(self,scr,*,use_256=False):
        self._colorpairs={}
        self._colorpair_next_index=1
        self._scr=scr
        self._color_lookup_cache={}
        self._erase_pending=True
        if use_256 and curses.COLORS<256:
            raise RuntimeError("Terminal does not support 256colors!")
        self._256c=use_256
    def rgb_to_colornum(self,rgb):
        assert self._256c
        if rgb not in self._color_lookup_cache:
            closest=_rgb_to_256c(*rgb)
            self._color_lookup_cache[rgb]=closest
        return self._color_lookup_cache[rgb]
    def check_numcolors(self):
        cdefs=[]
        for i in range(curses.COLORS):
            cdefs.append(curses.color_content(i))
        return len(set(cdefs))
    def _color_to_colornum(self,c):
        if type(c)==int:
            if not (0<=c<curses.COLORS):
                raise ValueError("Out-of-range color constant: "+str(c))
            return c
        elif type(c) in (tuple,list):
            if not self._256c:
                raise ValueError("Must enable 256colors for RGB input!")
            if len(c)!=3:
                raise ValueError("Invalid RGB color: "+str(c))
            if max(c)>1 or min(c)<0:
                raise ValueError("Each color component must be in range 0~1: "+str(c))
            return self.rgb_to_colornum(c)
        else:
            raise ValueError("Invalid color: "+str(c))

    def add(self,x,y,s,*,
            fg=curses.COLOR_WHITE,bg=curses.COLOR_BLACK,
            attrs=()):
        xmax=curses.COLS-1
        ymax=curses.LINES-1
        if x<0 or (x+len(s))>xmax or y<0 or y>ymax:
            raise TextOutOfBounds

        if self._erase_pending:
            self._scr.erase()
            self._erase_pending=False

        fg_colornum=self._color_to_colornum(fg)
        bg_colornum=self._color_to_colornum(bg)

        assert 0<=fg_colornum<256
        colorpair=(fg_colornum,bg_colornum)
        if colorpair not in self._colorpairs:
            curses.init_pair(self._colorpair_next_index, *colorpair)
            self._colorpairs[colorpair]=self._colorpair_next_index
            self._colorpair_next_index+=1

        attr_bitfield=curses.color_pair(self._colorpairs[colorpair])
        for attr in attrs:
            attr_bitfield=attr_bitfield | attr
        self._scr.addstr(y,x,s,attr_bitfield)
    def commit(self,erase=True):
        self._scr.refresh()
        if erase:
            self._erase_pending=True
    def getkey(self):
        res=None
        try:
            res= self._scr.getkey()
        except:
            pass
        return res
    def subscreen(self,xdelta,ydelta):
        return CYSub(self,xdelta,ydelta)

class CYSub():
    def __init__(self,cy,xoff,yoff):
        self._cy=cy
        self._xoff=xoff
        self._yoff=yoff
    def add(self,x,y,*args,**kwargs):
        self._cy.add(
            x+self._xoff,
            y+self._yoff,
            *args,**kwargs
            )
    def subscreen(self,xdelta,ydelta):
        return CYSub(self._cy,
                     self._xoff+xdelta,
                     self._yoff+ydelta)

if __name__=="__main__":
    import time
    with CurseYouEnviornment(use_256color=True) as cy:
        r,g,b=0,0,0
        for i in range(20):
            cy.add(0,0,
                "keypress:"+str(cy.getkey()))
            cy.add(20,0,
                "NC:"+str(cy.check_numcolors()))

            cys=cy.subscreen(0,i%10+1)
            cys.add(i,0,"RAINBOW!",
                    fg=(r,g,b))
            r=(r+0.1)%1
            g=(g+0.7)%1
            b=(b+0.3)%1

            cys2=cy.subscreen(30,1)
            for ri in range(10):
                for gi in range(10):

                    cys2.add(ri*2,gi,"\u2588"*2,
                             fg=(ri/9,gi/9,(i%10)/9))


            cy.commit()
            time.sleep(0.5)
