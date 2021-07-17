import random
import enum
import copy
import curses
import time

class Tuples:
    @classmethod
    def sub(cls,a,b):
        return cls.add(a,cls.neg(b))
    @classmethod
    def add(cls,a,b):
        return cls.forelem2(a,b,lambda x,y:x+y)
    @classmethod
    def neg(cls,a):
        return cls.forelem(a,lambda x:-x)
    @classmethod
    def forelem(cls,a,f):
        return tuple((f(i) for i in a))
    @classmethod
    def forelem2(cls,a,b,f):
        if len(a)!=len(b):
            raise Exception("Mismatched tuple length")
        return tuple((f(a[i],b[i]) for i in range(len(a))))


class Block():
    '''
    Class representing a single block in the matrix.
    Immutable.
    '''
    def __init__(self,solid=True,source="X"):
        self._solid=solid
        self._source=source
    @property
    def solid(self):
        return self._solid
    @property
    def source(self):
        return self._source

    def __repr__(self):
        return F"Block(solid={self.solid},source={self.source})"

class RasterOutOfBoundsException(Exception):
    pass

class ImmutableModificationException(Exception):
    pass

class Pixel2DSet():
    '''
    Class represneting a set of blocks. Immutable.
    Note that unlike Raster2D this does nont need to be a square.
    '''
    def __init__(self):
        self._pixels=dict()
    def __iter__(self):
        return self._pixels.__iter__()
    def __getitem__(self,k):
        return self._pixels[k]
    def translate(self,x,y):
        res = Pixel2DSet()
        for coords in self:
            oc=coords
            nc=(oc[0]+x,oc[1]+y)
            res._pixels[nc]=self._pixels[oc]
        return res
    


    @classmethod
    def from_dict(cls,d):
        dat=copy.copy(d)
        res=Pixel2DSet()
        res._pixels=dat
        return res

    @classmethod
    def from_r2d(cls,r2d):
        res=Pixel2DSet()
        
        for coords in r2d:
            res._pixels[coords]=r2d[coords]
        return res
    
    @classmethod
    def from_string(cls,*args,fill=Block()):
        '''
        #=filled, @=center, !=center unfilled
        '''

        s="\n".join(args)

        res=Pixel2DSet()

        center_coords=(0,0)
        ss=s.split("\n")

        lineN=len(ss)
        for lineI in range(len(ss)):
            lineS=ss[lineI]
            for colI in range(len(lineS)):
                ch=lineS[colI]
                co=(colI,lineN-lineI-1)

                if ch=="#" or ch=="@":
                    res._pixels[co]=fill
                    
                if ch=="@" or ch=="!":
                    center_coords=co
                
                
                
        res=res.translate(*Tuples.neg(center_coords))
        
        return res

    def __str__(self):
        return "Pixel2DSet with pixels:\n"+"\n".join(("  "+str(self[i]) for i in self))


    

class Raster2D():
    '''
    Represents a rectangular grid of blocks. Immutable.
    Must receive the X,Y dimensions with a list/tuple with the exact size 
    '''
    def __init__(self,x,y,data):
        self._x=x
        self._y=y
        self._dataN=x*y

        self._data=tuple(data)
        
        if len(self._data)!=self._dataN:
            raise ValueError


    @property
    def x(self):
        return self._x
    @property
    def y(self):
        return self._y

    def __iter__(self):

        for y in range(self._y):
            for x in range(self._x):
                yield (x,y)


    def _coord_to_idx(self,x,y):
        if x<0 or x>=self._x or y<0 or y>=self._y:
            raise RasterOutOfBoundsException("converted",x,y,"in a Raster2D of dimension",self._x,self._y)
        return x+y*self._x

    def composite_p2ds(self,p2ds):
        newdata=list(self._data)
        for coords in p2ds:
            newdata[self._coord_to_idx(*coords)]=p2ds[coords]

        return Raster2D(self._x,self._y,newdata)



    def crop(self,bbox):
        # coordinates are inclusive
        x_min,y_min,x_max,y_max=bbox
        
        x_size=x_max-x_min+1
        y_size=y_max-y_min+1

        cropdata=[]
        for y in range(y_min,y_max+1):
            for x in range(x_min,x_max+1):
                cropdata.append(self[(x,y)])

        return Raster2D(x_size,y_size,cropdata)
            
        
    
    def __getitem__(self,c):
        idx=self._coord_to_idx(c[0],c[1])
        return self._data[idx]
    def __setitem__(self,c,val):
        raise ImmutableModificationException

    @classmethod
    def blank_fill(cls,x,y,blank):
        return Raster2D(x,y,(blank,)*(x*y))



class OOBFilledRaster2D(Raster2D):
    def __init__(self,r2d,oob):
        self._r2d=r2d
        self._oob=oob
    def __getitem__(self,c):
        try:
            return self._r2d[c]
        except RasterOutOfBoundsException:
            return self._oob



class BagRandomizer():
    def __init__(self, minos=()):
        self.buffer=[]
        self._minos=minos
    def __iter__(self):
        return self
    def __next__(self):
        return self.generate_next()
    def generate_next(self):
        if not self.buffer: #empty!
            l=list(self._minos)
            random.shuffle(l)
            self.buffer+=l

        res=self.buffer[0]
        del self.buffer[0]
        return res
            
class GameConstants:
    lockdown_delay=0.5

class Tetrimino():
    def __init__(self, coords, rotation, playfield):
        self._coords=coords
        self._rotation=rotation
        self._playfield=playfield
        self._playfield.add_activemino(self)
        self._lockdown_timer_start=playfield.get_game_time()
        self._gravity_remainder=0
        self._dead=False

    def die(self):
        self._dead=True
    @property
    def dead(self):
        return self._dead

    def is_immobile(self):
        ms=self._matrix_state()
        for delta in ((1,0),(-1,0),(0,1),(0,-1)):
            
            temp_mino=copy.copy(self)
            temp_mino._translate(*delta)
            
            blocks=temp_mino.get_blocks()
            if not self.overlap(ms,blocks):
                return False
        return True
        

    def get_blocks(self):
        p2ds=self.shape()
        return p2ds.translate(*self._coords)
    def shape(self):
        raise NotImplementedError
    def _translate(self,x,y):
        self._coords=Tuples.add(self._coords,(x,y))
    def _kicks(self,old_rotation,new_rotation):
        raise NotImplementedError

    
    def _rotate(self,rot,r2d):
        if not(rot==1 or rot==-1):
            raise Exception("Invalid rotation delta!")
        
        temp_mino=copy.copy(self)
        
        old_rotation=self._rotation
        new_rotation=(old_rotation+rot)%4
        
        temp_mino._rotation=new_rotation
        
        kick_tests=temp_mino._kicks(old_rotation,new_rotation)
        for kt in kick_tests:
            temp2_mino=copy.copy(temp_mino)
            temp2_mino._translate(kt[0],kt[1])
            blocks=temp2_mino.get_blocks()
            if not self.overlap(r2d,blocks):
                #test pass!
                self._coords=temp2_mino._coords
                self._rotation=temp2_mino._rotation
                break
    

    @classmethod
    def overlap(cls,r2d,p2ds):
        for bcoords in p2ds:
            if r2d[bcoords].solid==True:
                return True
        return False
        
    def _try_move(self,delta_x,delta_y):
        temp_mino=copy.copy(self)
        temp_mino._translate(delta_x,delta_y)
        blocks=temp_mino.get_blocks()
        matrix_state=self._matrix_state()

        if self.overlap(matrix_state,blocks):
            return False
        
 
        #Can go
        self._coords=temp_mino._coords
        return True

    def firm_drop(self):
        while self._try_move(0,-1):
            pass
    
    def hard_drop(self):
        self.firm_drop()
        self._playfield.lock_mino(self)
        
    
    def gravity(self,n):
        move_success=self._try_move(0,-1)
        
        if move_success:
            self._lockdown_timer_start=self._playfield.get_game_time()

        if n>1:
            self._gravity(n-1)

    def _matrix_state(self):
        return OOBFilledRaster2D(
                    self._playfield.get_matrix_state(
                        player_filter= lambda player: not (player is self))
                    ,oob=Block(solid=True))
    
    def input(self,
              rotate_r=False,rotate_l=False,
              hard=False,soft=False,left=False,right=False):
        matrix_state=self._matrix_state()
        if rotate_r:
            self._rotate(+1,matrix_state)
        elif rotate_l:
            self._rotate(-1,matrix_state)

        if hard:
            self.hard_drop()
        elif soft:
            self.firm_drop()#gravity(1)
        elif left:
            self._try_move(-1,0)
        elif right:
            self._try_move(+1,0)

        
# http://harddrop.com/wiki/SRS#How_Guideline_SRS_Really_Works
class SRS_Tetrimino(Tetrimino):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
    def _kicks(self, old_rotation, new_rotation):
        res=[]
        kick_offsets=self._SRS_kick_offsets()

        for offsets in kick_offsets:
            o=offsets[old_rotation]
            n=offsets[new_rotation]
            res.append(Tuples.sub(o,n))

        return res
            
    def _SRS_kick_offsets(self):
        raise NotImplementedError
    
_SRS_Kicks_JLSTZ=(((0,0),(0,0),(0,0),(0,0)), #No kick
                  ((0,0),(1,0),(0,0),(-1,0)), #Kick 1
                  ((0,0),(+1,-1),(0,0),(-1,-1)), #Kick 2
                  ((0,0),(0,2),(0,0),(0,+2)), #Kick 3
                  ((0,0),(1,2),(0,0),(-1,2))) #Kick 4
_SRS_Shapes_T=[None]*4
_SRS_Shapes_T[0]=Pixel2DSet.from_string(" # ",
                                        "#@#")
_SRS_Shapes_T[1]=Pixel2DSet.from_string("# ",
                                        "@#",
                                        "# ")
_SRS_Shapes_T[2]=Pixel2DSet.from_string("#@#",
                                        " # ")
_SRS_Shapes_T[3]=Pixel2DSet.from_string(" #",
                                        "#@",
                                        " #")


_SRS_Shapes_L=[None]*4
_SRS_Shapes_L[0]=Pixel2DSet.from_string("  #",
                                        "#@#")
_SRS_Shapes_L[1]=Pixel2DSet.from_string("# ",
                                        "@ ",
                                        "##")
_SRS_Shapes_L[2]=Pixel2DSet.from_string("#@#",
                                        "#  ")
_SRS_Shapes_L[3]=Pixel2DSet.from_string("##",
                                        " @",
                                        " #")

_SRS_Shapes_J=[None]*4
_SRS_Shapes_J[0]=Pixel2DSet.from_string("#  ",
                                        "#@#")
_SRS_Shapes_J[1]=Pixel2DSet.from_string("##",
                                        "@ ",
                                        "# ")
_SRS_Shapes_J[2]=Pixel2DSet.from_string("#@#",
                                        "  #")
_SRS_Shapes_J[3]=Pixel2DSet.from_string(" #",
                                        " @",
                                        "##")

_SRS_Shapes_S=[None]*4
_SRS_Shapes_S[0]=Pixel2DSet.from_string(" ##",
                                        "#@ ")
_SRS_Shapes_S[1]=Pixel2DSet.from_string("# ",
                                        "@#",
                                        " #")
_SRS_Shapes_S[2]=Pixel2DSet.from_string(" @#",
                                        "## ")
_SRS_Shapes_S[3]=Pixel2DSet.from_string("# ",
                                        "#@",
                                        " #")

_SRS_Shapes_Z=[None]*4
_SRS_Shapes_Z[0]=Pixel2DSet.from_string("## ",
                                        " @#")
_SRS_Shapes_Z[1]=Pixel2DSet.from_string(" #",
                                        "@#",
                                        "# ")
_SRS_Shapes_Z[2]=Pixel2DSet.from_string("#@ ",
                                        " ##")
_SRS_Shapes_Z[3]=Pixel2DSet.from_string(" #",
                                        "#@",
                                        "# ")

_SRS_Kicks_I=(((0,0),(-1,0),(-1,1),(0,1)), #No kick
              ((-1,0),(0,0),(1,1),(0,1)), #Kick 1
               ((2,0),(0,0),(-2,1),(0,1)), #Kick 2
               ((-1,0),(0,1),(1,0),(0,-1)), #Kick 3
               ((2,0),(0,-2),(-2,0),(0,2))) #Kick 4

_SRS_Shapes_I=[None]*4
_SRS_Shapes_I[0]=Pixel2DSet.from_string("#@##")
_SRS_Shapes_I[1]=Pixel2DSet.from_string("#",
                                        "@",
                                        "#",
                                        "#")
_SRS_Shapes_I[2]=Pixel2DSet.from_string("##@#")
_SRS_Shapes_I[3]=Pixel2DSet.from_string("#",
                                        "#",
                                        "@",
                                        "#")

_SRS_Kicks_O=(((0,0),(0,-1),(-1,-1),(-1,0)),) #No kick
_SRS_Shapes_O=[None]*4
_SRS_Shapes_O[0]=Pixel2DSet.from_string("##",
                                        "@#")
_SRS_Shapes_O[1]=Pixel2DSet.from_string("@#",
                                        "##")
_SRS_Shapes_O[2]=Pixel2DSet.from_string("#@",
                                        "##")
_SRS_Shapes_O[3]=Pixel2DSet.from_string("##",
                                        "#@")


class SRS_J(SRS_Tetrimino):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        
    def shape(self):
        return _SRS_Shapes_J[self._rotation]
    def _SRS_kick_offsets(self):
        return _SRS_Kicks_JLSTZ
class SRS_L(SRS_Tetrimino):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        
    def shape(self):
        return _SRS_Shapes_L[self._rotation]
    def _SRS_kick_offsets(self):
        return _SRS_Kicks_JLSTZ
class SRS_S(SRS_Tetrimino):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        
    def shape(self):
        return _SRS_Shapes_S[self._rotation]
    def _SRS_kick_offsets(self):
        return _SRS_Kicks_JLSTZ
class SRS_T(SRS_Tetrimino):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        
    def shape(self):
        return _SRS_Shapes_T[self._rotation]
    def _SRS_kick_offsets(self):
        return _SRS_Kicks_JLSTZ
class SRS_Z(SRS_Tetrimino):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        
    def shape(self):
        return _SRS_Shapes_Z[self._rotation]
    def _SRS_kick_offsets(self):
        return _SRS_Kicks_JLSTZ
    
class SRS_I(SRS_Tetrimino):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        
    def shape(self):
        return _SRS_Shapes_I[self._rotation]
    def _SRS_kick_offsets(self):
        return _SRS_Kicks_I
    
class SRS_O(SRS_Tetrimino):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        
    def shape(self):
        return _SRS_Shapes_O[self._rotation]
    def _SRS_kick_offsets(self):
        return _SRS_Kicks_O
SevenBagRandomizer=BagRandomizer((SRS_J,SRS_L,SRS_S,SRS_T,SRS_Z,SRS_I,SRS_O))

class LineClear():

    def __init__(self):
        self.lines=0
        self.spin=False

    def plus_line(self):
        self.lines+=1

    def activate_spin(self):
        self.spin=True

    @property
    def empty(self):
        return self.lines==0

    def __str__(self):
        s={
            1:"Single",
            2:"Double",
            3:"Triple",
            4:"QUADRUPLE"}[self.lines]
        if self.spin:
            s+=" +TWIST"
        return s

class Playfield():
    def __init__(self,dim_x,dim_y):
        self._dim_x=dim_x
        self._dim_y=dim_y
        self._matrix=Raster2D.blank_fill(dim_x,dim_y,Block(solid=False))
        self._active_minos=list()
        

    def add_activemino(self,mino):
        self._active_minos.append(mino)

    def get_matrix_state(self,*,player_filter=(lambda x:True)):
        r2d=self._matrix
        for i in  self._active_minos:
            if player_filter(i):
                r2d=r2d.composite_p2ds(i.get_blocks())
        return r2d
        
    def update_matrix(self,newmat):
        self._matrix=newmat
    def gravity(self):
        pass

    def line_clear(self,y):
        lower=self._matrix.crop((0,0,self._dim_x-1,y-1))
        lower_p2ds=Pixel2DSet.from_r2d(lower).translate(0,0)
        upper=self._matrix.crop((0,y+1,self._dim_x-1,self._dim_y-1))
        upper_p2ds=Pixel2DSet.from_r2d(upper).translate(0,y)
        #print(lower_p2ds)
        
        self._matrix=Raster2D.blank_fill(self._dim_x,self._dim_y,Block(solid=False))
        
        self._matrix=self._matrix.composite_p2ds(lower_p2ds)
        self._matrix=self._matrix.composite_p2ds(upper_p2ds)
        
    def check_line_clear(self):
        lc=LineClear()
        while True:
            line_cleared=False
            for y in range(self._matrix.y):
                for x in range(self._matrix.x):
                    if self._matrix[(x,y)].solid==False:
                        break
                else: # no break occurred in loop - line is filled!
                    self.line_clear(y)
                    lc.plus_line()
                    line_cleared=True
                    break
            
            if not line_cleared:
                break
        return lc
                
        

    def get_game_time(self):
        # seconds
        pass

    def remove_mino(self,mino):
        self._active_minos.remove(mino)
    
    def lock_mino(self,mino):
        if mino not in self._active_minos:
            raise Exception("what")

        imm=mino.is_immobile()
        self._matrix=self._matrix.composite_p2ds(mino.get_blocks())
        mino.die()
        self.remove_mino(mino)
        
        lc=self.check_line_clear()
        if imm:
            lc.activate_spin()
        if not lc.empty:
            print(lc)

    def force_matrix_state(self,r2d):
        self._matrix=r2d





def r2d_render_stdout(self, r2d):
    def _b2t(self,block):
        if block.solid:
            return block.source[0].upper()
        else:
            return " "
    res=''
    res+="+"+"-"*r2d.x+"+"+"\n"
    for y in range(r2d.y):
        iy=r2d.y-y-1
        res+="|"
        for x in range(r2d.x):
            coords=(x,iy)
            block=r2d[coords]
            res+=self._b2t(block)
        res+="|"
        res+="\n"
    res+="+"+"-"*r2d.x+"+"
    print(res)

def r2d_render_curses(self, r2d, scr, x, y):
    pass

_test_DT_cannon_p2ds=Pixel2DSet.from_string(
    "  ##      ",
    "   #      ",
    "## #######",
    "#  #######",
    "#   ######",
    "## #######",
    "@# #######"
    )
_test_DT_cannon_r2d=Raster2D.blank_fill(10,20,Block(solid=False)).composite_p2ds(_test_DT_cannon_p2ds.translate(0,0))


class TextOutOfBounds(BaseException):
    pass

class CurseYou:
    '''
    Thin wrapper around curses module...
    '''
    def __init__(self,scr):
        self._colorpairs={}
        self._colorpair_next_index=1
        self._scr=scr
    def add(self,x,y,s,fg,bg,*attrs):
        xmax=curses.COLS-1
        ymax=curses.LINES-1
        if x<0 or x>xmax or y<0 or y>ymax:
            raise TextOutOfBounds

        if (fg,bg) not in self._colorpairs:
            curses.init_pair(self._colorpair_next_index,fg,bg)
            self._colorpairs[(fg,bg)]=self._colorpair_next_index
            self._colorpair_next_index+=1

        attr_bitfield=curses.color_pair(self._colorpairs[(fg,bg)])
        for attr in attrs:
            attr_bitfield=attr_bitfield | attr
        self._scr.addstr(y,x,s,attr_bitfield)
    def commit(self):
        self._scr.refresh()
    def getkey():
        pass

def main(stdscr):
    stdscr.nodelay(True)
    cy=CurseYou(stdscr)

    sbr=SevenBagRandomizer
    pf=Playfield(10,20)

    pf.force_matrix_state(_test_DT_cannon_r2d)

    mino=SRS_T((5,15),0,pf)
    '''
    while True:
        if mino.dead:
            mino=sbr.generate_next()((5,17),0,pf)

        pttr.render(pf.get_matrix_state())

        inp=input()
        if inp=="a":
            mino.input(left=True)
        elif inp=="d":
            mino.input(right=True)
        elif inp=="w":
            mino.input(hard=True)
        elif inp=="s":
            mino.input(soft=True)
        elif inp=="q":
            mino.input(rotate_l=True)
        elif inp=="e":
            mino.input(rotate_r=True)
            '''

    target_fps=20
    target_spf=1/target_fps
    last_frame_time=0
    while True: # UI loop
        t=time.time()
        target_frametime=last_frame_time+target_spf
        waittime=target_frametime-t
        if waittime<=0:
            pass
        elif waittime>target_spf:
            time.sleep(target_spf)
        else:
            time.sleep(waittime)

        try:
            inp=stdscr.getkey().upper()
        except:
            inp=None


        if mino.dead:
            mino=sbr.generate_next()((5,17),0,pf)

        if inp=="A":
            mino.input(left=True)
        elif inp=="D":
            mino.input(right=True)
        elif inp=="W":
            mino.input(hard=True)
        elif inp=="S":
            mino.input(soft=True)
        elif inp=="Q":
            mino.input(rotate_l=True)
        elif inp=="E":
            mino.input(rotate_r=True)

        r2d=pf.get_matrix_state()
        #stdscr.clear()
        for x,y in r2d:
            cy.add(x,r2d.y-y,
                [" ","%"][r2d[x,y].solid],
                curses.COLOR_RED,curses.COLOR_WHITE,
                curses.A_BLINK)






        cy.commit()



if __name__=="__main__":
    curses.wrapper(main)



















