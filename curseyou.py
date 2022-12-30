import curses

'''
Thin-ish wrapper around the curses module.

Usage example:

with curseyou.CurseYouEnvironment(use_256color=True) as cy:
    for i in range(10):
        time.sleep(0.5)
        style=curseyou.CYStyle(fg=(1.0,0.5,0),
                               bg=curseyou.CYStyle.BLACK,
                               bold=True)
        cy.add(1,0,"Hello",style=style)
        subview=cy.subview(2,1)
        style.bg=(0,0,1)
        subview.add(0,0,str(cy.getkey()),style=style)
        cy.commit()
'''

class CurseYouEnvironment:
    '''
    Context manager for curses.
    When entered, setup curses environment, and return a CurseYou object.
    '''
    def __init__(self, use_256color=False):
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
        if self._256c and curses.COLORS<256:
            raise RuntimeError("256 colors not supported!")
        return CurseYou(stdscr,use_256=self._256c)

    def __exit__(self, exc_type, exc_value, traceback):
        if self._stdscr is not None:
            self._stdscr.keypad(False)
        curses.echo()
        curses.nocbreak()
        curses.endwin()


class CYStyle:
    '''
    Represents a text style. May be supplied to CYView.add()
    available members:
        .fg .bg = color constant e.g. CYStyle.WHITE or RGB tuple e.g. (0.3,0.0,1.0)
        .bold .dim .blink = boolean values.
    '''
    WHITE   = curses.COLOR_WHITE
    BLACK   = curses.COLOR_BLACK
    BLUE    = curses.COLOR_BLUE
    CYAN    = curses.COLOR_CYAN
    GREEN   = curses.COLOR_GREEN
    MAGENTA = curses.COLOR_MAGENTA
    RED     = curses.COLOR_RED
    YELLOW  = curses.COLOR_YELLOW

    def __init__(self,*,
                 fg=curses.COLOR_WHITE,
                 bg=curses.COLOR_BLACK,
                 bold=False,
                 dim=False,
                 blink=False,
                 attrs=()):
        self._fg=fg
        self._bg=bg
        self._attrs=set(attrs)

        self.bold=bold
        self.dim=dim
        self.blink=blink

    @property
    def fg(self):
        return self._fg
    @fg.setter
    def fg(self,v):
        self._fg=v

    @property
    def bg(self):
        return self._bg
    @bg.setter
    def bg(self,v):
        self._bg=v

    @property
    def attrs(self):
        return tuple(self._attrs)

    def _remove_attr(self,*attributes):
        for i in attributes:
            if i in self._attrs:
                self._attrs.remove(i)
    def _add_attr(self,*attributes):
        for i in attributes:
            self._attrs.add(i)

    @property
    def bold(self):
        return curses.A_BOLD in self._attrs
    @bold.setter
    def bold(self,b):
        if b:
            self._add_attr(curses.A_BOLD)
            self._remove_attr(curses.A_DIM)
        else:
            self._remove_attr(curses.A_BOLD)

    @property
    def dim(self):
        return curses.A_DIM in self._attrs
    @dim.setter
    def dim(self,b):
        if b:
            self._add_attr(curses.A_DIM)
            self._remove_attr(curses.A_BOLD)
        else:
            self._remove_attr(curses.A_DIM)

    @property
    def blink(self):
        return curses.A_BLINK in self._attrs
    @blink.setter
    def blink(self,b):
        if b:
            self._add_attr(curses.A_BLINK)
        else:
            self._remove_attr(curses.A_BLINK)


def _256c_to_rgb(n):
    assert 16<=n<=231
    n=n-16
    b=n%6
    n=n//6
    g=n%6
    n=n//6
    r=n
    return (r/6,g/6,b/6)

def _rgb_to_256c(r,g,b):
    rn=round(r*5)
    gn=round(g*5)
    bn=round(b*5)
    res= 16 + 36*rn + 6*gn + bn
    assert 16<=res<=231
    return res

class TextOutOfBounds(BaseException):
    pass
class InvalidTextError(BaseException):
    pass


class CYView():
    '''
    Class for representing a "view" you can write on.
    May have a bounding box, and may have a coordinate offset.
    Do not initialize directly - use the subclass CurseYou object provided by CurseYouEnvironment.
    '''
    def __init__(self,*,cy_object,xoff=0,yoff=0,xsize=None,ysize=None):
        self._cy=cy_object
        self._xoff=xoff
        self._yoff=yoff
        self._xsize=xsize
        self._ysize=ysize

    def identify(self):
        return F"{self._xsize}x{self._ysize}+{self._xoff},{self._yoff}"
    def check_inbounds(self,x,y):
        neg_inbounds= (x>=0) and (y>=0)
        pos_inbounds= True
        if self._xsize is not None:
            pos_inbounds= pos_inbounds and (x<self._xsize)
        if self._ysize is not None:
            pos_inbounds= pos_inbounds and (y<self._ysize)
        return neg_inbounds and pos_inbounds

    def add(self,x,y,s,*args,**kwargs):
        '''
        Write text to the terminal, at coordinates (x,y).
        s must not contain a newline, and must fit in the view.
        fg,bg,attrs may be specified with a keyword argument,
        or a single CYStyle object can be supplied in the style keyword argument.
        '''
        # bounds check
        if "\n" in s:
            raise InvalidTextError(F"{repr(s)} contains newlines.")
        if (not self.check_inbounds(x,y)) or (not self.check_inbounds(x+len(s)-1,y)):
            raise TextOutOfBounds(F"Text {repr(s)} at ({x},{y}) out of bounds on screen "+self.identify())

        self._cy.write(
            x+self._xoff,
            y+self._yoff,
            s,*args,**kwargs)

    def subview(self,xdelta=0,ydelta=0,xsize=None,ysize=None):
        '''
        Create a "Sub-view" - a screen offset by a certain amount.
        For example, once you create a subview with an offset of (1,3),
        a write to coordinates (2,2) through that view will actually go to (3,5).
        Can be recursively created.
        '''

        # New subscreen must be contained within this screen
        inbounds=True
        inbounds=inbounds and self.check_inbounds(xdelta,ydelta)
        if self._xsize is not None:
            if self._xsize is None: # bound to unbound
                inbounds=False
            else:
                inbounds=inbounds and (xdelta+xsize)<=self._xsize
        if self._ysize is not None:
            if self._ysize is None: # bound to unbound
                inbounds=False
            else:
                inbounds=inbounds and (ydelta+ysize)<=self._ysize

        if not inbounds:
            raise TextOutOfBounds(F"Subscreen {xsize}x{ysize}+~{xdelta},~{ydelta} will not fit in parent screen "+self.identify())

        return CYView(cy_object=self._cy,
                      xoff=self._xoff+xdelta,
                      yoff=self._yoff+ydelta,
                      xsize=xsize,ysize=ysize)


class CurseYou(CYView):
    '''
    Object used for managing the terminal.
    Do not initialize directly. Instead, use the one provided by CurseYouEnvironment.__enter__()
    '''
    def __init__(self,scr,*,use_256=False):
        super().__init__(cy_object=self)

        self._colorpairs={}
        self._colorpair_next_index=1
        self._firstdraw=True

        self._scr=scr
        self._256c=use_256

    def _color_to_colornum(self,c):
        if type(c)==int:
            # Direct color constant used by curses.
            if not (0<=c<curses.COLORS):
                raise ValueError("Out-of-range color constant: "+str(c))
            return c
        elif type(c) in (tuple,list):
            # RGB color
            if not self._256c:
                raise ValueError("Must enable 256colors for RGB input!")
            if len(c)!=3:
                raise ValueError("Invalid RGB color: "+str(c))
            if max(c)>1 or min(c)<0:
                raise ValueError("Each color component must be in range 0~1: "+str(c))
            return _rgb_to_256c(*c)
        else:
            # Something else?
            raise ValueError("Invalid color: "+str(c))

    def write(self,x,y,s,*,
            fg=curses.COLOR_WHITE,bg=curses.COLOR_BLACK,
            attrs=(),
            style=None):

        # Erase if first write of the frame.
        if self._firstdraw:
            self._scr.erase()
            curses.update_lines_cols()
            self._firstdraw=False

        # Bounds checking
        xmax=curses.COLS-1
        ymax=curses.LINES-1
        if x<0 or (x+len(s))>xmax or y<0 or y>ymax:
            raise TextOutOfBounds(F"Text {repr(s)} at ({x},{y}) out of bounds ({xmax},{ymax})")
        if "\n" in s:
            raise InvalidTextError(F"{repr(s)} contains newlines.")

        # Styles computation
        if style is not None:
            fg=style.fg
            bg=style.bg
            attrs=style.attrs

        fg_colornum=self._color_to_colornum(fg)
        bg_colornum=self._color_to_colornum(bg)

        # Initialize color pair if new
        colorpair=(fg_colornum,bg_colornum)
        if colorpair not in self._colorpairs:
            curses.init_pair(self._colorpair_next_index, *colorpair)
            self._colorpairs[colorpair]=self._colorpair_next_index
            self._colorpair_next_index+=1

        # Add the attributes to the color pair
        attr_bitfield=curses.color_pair(self._colorpairs[colorpair])
        for attr in attrs:
            attr_bitfield=attr_bitfield | attr

        # Actually write
        self._scr.addstr(y,x,s,attr_bitfield)

    def commit(self):
        '''
        Commit all the changes to the screen.
        '''
        self._scr.refresh()
        self._firstdraw=True

    def getkey(self):
        '''
        Get all the key presses that happened after the last call to this function.
        All the keys that were pressed will be returned, in order, in a tuple.

        Due to the limitation of curses, we can only receive key press events,
        and not key release events.
        '''
        res=[]
        try:
            while True:
                res.append(self._scr.getkey())
        except:
            pass
        return tuple(res)






if __name__=="__main__":
    import time
    with CurseYouEnvironment(use_256color=True) as cy:
        r,g,b=0,0,0
        for i in range(20):
            cy.add(0,0,
                "keypress:"+str(cy.getkey()),
                style=CYStyle(fg=curses.COLOR_RED,blink=True))

            cys=cy.subview(0,i%10+1)
            cys.add(i,0,"RAINBOW!",
                    fg=(r,g,b))
            r=(r+0.1)%1
            g=(g+0.7)%1
            b=(b+0.3)%1

            cys2=cy.subview(30,1)
            for ri in range(10):
                for gi in range(10):

                    cys2.add(ri*2,gi,"\u2588"*2,
                             fg=(ri/9,gi/9,(i%10)/9))


            cy.commit()
            time.sleep(0.5)
