"""
This module contains an implementation of the Image Source Method (ISM).
"""

from heapq import nlargest
from geometry import Point, Plane, Polygon
from ._ism import Wall, Mirror, is_shadowed, test_effectiveness
import logging
from cytoolz import unique, count
import numpy as np

# To render the geometry
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Patch3DCollection
from ._tools import Arrow3D
from matplotlib import animation


def amount_of_sources(order, walls):
    """The amount of potential sources :math:`N` up to a certain order :math:`o` for a given amount of walls :math:`w`.
    
    :param order: Order threshold :math:`o`.
    :param walls: Amount of walls :math:`w`.
    
    :rtype: int
    
    The amount of potential sources :math:`N` is given by
    
    .. math:: N = 1 + \\sum w \\left( w-1 \\right)^{o-1}
    
    
    """
    return 1 + sum((walls*(walls-1)**(o-1) for o in range(1, order+1)))
    
    
    

class Model(object):
    """The `Model` is the main class used for determining mirror sources and their effectiveness.
    
    This implementation requires a fixed source position. The receiver position can vary.
    """

    def __init__(self, walls, source, receiver, max_order=3):#, max_distance=1000.0, min_amplitude=0.01):
        
        self.walls = walls
        """Walls
        """
        
        self.source = source
        """Source position. Requires a list of points.
        
        The source cannot move.
        
        ##Required is an instance of :class:`geometry.Point`
        """
        
        self.receiver = receiver
        """Receiver position. Requires a list of points.
        
        The receiver can move.

        ##Required is a list of instances of :class:`geometry.Point`
        """
        
        self.max_order = max_order
        """Order threshold. Highest order to include.
        """
  
    @property
    def source(self):
        return self._source
    
    @source.setter
    def source(self, x):
        if isinstance(x, list):
            self._source = x
        elif(isinstance(x, np.ndarray)):
            self._source = [Point(*row) for row in x]
        else:
            raise ValueError("List of Point instances are required.")
    
    @property
    def receiver(self):
        return self._receiver
    
    @receiver.setter
    def receiver(self, x):
        if isinstance(x, list):
            self._receiver = x
        elif(isinstance(x, np.ndarray)):
            self._receiver = [Point(*row) for row in x]
        else:
            raise ValueError("List of Point instances are required.")
        
    @property
    def is_source_moving(self):
        return count(unique(self.source, key=tuple)) != 1
        
    @property
    def is_receiver_moving(self):
        return count(unique(self.receiver, key=tuple)) != 1
        
  
    def mirrors(self):
        """Mirrors.
        
        Determine the mirrors of non-moving source. Whether the mirrors are effective can be obtained using :meth:`determine`.
        
        In order to determine the mirrors a receiver position is required. The first receiver location is chosen.
        """
        if not self.walls:
            raise ValueError("ISM cannot run without any walls.")
        
        yield from ism(self.walls, self.source[0], self.receiver[0], self.max_order)
    
    def _determine(self, mirrors):
        """Determine mirror source effectiveness and strength.
        """
        #r = 1 if isinstance(self.receiver, Point) else len(self.receiver)
        n_positions = len(self.receiver)
        n_frequencies = len(self.walls[0].impedance)
        
        #amount_of_receiver_positions = r

        while True:
            mirror = next(mirrors)
            mirror.effective = np.empty(n_positions, dtype='int32')#, dtype='bool')
            mirror.distance = np.empty(n_positions, dtype='float64')
            mirror.strength = np.ones((n_positions, n_frequencies), dtype='complex128')

            for t in range(n_positions):
                if mirror.mother is not None:
                    mother_strength = mirror.mother.strength[t]
                else:
                    mother_strength = np.ones((n_frequencies), dtype='complex128')
                    
                mirror.effective[t], mirror.strength[t], mirror.distance[t] = test_effectiveness(self.walls, 
                                                                                                 self.source[0], 
                                                                                                 self.receiver[t], 
                                                                                                 mirror.position, 
                                                                                                 mirror.wall, 
                                                                                                 mother_strength)

            yield mirror
    
    @staticmethod
    def _strongest(mirrors, amount):
        """Determine strongest mirror sources.
        
        :returns: Generator yielding sorted values.
        
        """
        yield from nlargest(amount, mirrors, key=lambda x:x.strength.max())
        #results = list()
        #for mirror in mirrors:
            #results.sort(key=lambda x:x.strength.max(), reverse=True)
            #for i, result in enumerate(results):
                #if (mirror.strength > result.strength).any():
                    #results.insert(i, mirror)
                    #if len(results) > amount:
                        #del results[-1]
            #else:
                #if len(results) < amount:
                    #results.append(mirror)
        #yield from results
    
    def determine(self, strongest=None):
        """Determine.
        """
        if not self.walls:
            raise ValueError("ISM cannot run without any walls.")
        #self.determine_mirrors()
        logging.info("determine: Determining mirror sources.")
        mirrors = self.mirrors()
        logging.info("determine: Determining mirror sources strength and effectiveness.")
        mirrors = self._determine(mirrors)
        if strongest:
            logging.info("determine: Determining strongest mirror sources.")
            mirrors = self._strongest(mirrors, strongest)
        yield from mirrors
    
    def plot(self, **kwargs):
        return plot_model(self, **kwargs)
        
    def plot_walls(self, filename=None):
        """
        Render of the walls. See :def:`plot_walls`.
        """
        return plot_walls(self.walls, filename)
    
    
def ism(walls, source_position, receiver_position, max_order=3):
    """Image source method.
    
    :param walls: List of walls
    :param source: Position of Source
    :param receiver: Position of Receiver
    :param max_order: Maximum order to determine image sources for.
    :param max_distance: Maximum distance
    :param max_amplitude: Maximum amplitude
    """
    logging.info("Start calculating image sources.")

    n_walls = len(walls)
    
    source_receiver_distance = source_position.distance_to(receiver_position)

    mirrors = list()
    """List of lists with mirror sources where ``mirrors[order]`` is a list of mirror sources of order ``order``"""
    
    """Step 3: Include the original source."""
    """Test first whether there is a direct path."""
    
    
    logging.info("Main source effective: {}".format(not is_shadowed(source_position, receiver_position, walls)))
    
    #mirrors.append([Mirror(source_position, 
                           #None, 
                           #None,
                           #0,
                           #source_position.distance_to(receiver_position), 
                           #np.ones_like(walls[0].impedance), 
                           #not is_shadowed(source_position, receiver_position, walls)
                           #)])
    
    mirrors.append([Mirror(source_position, mother=None, wall=None, order=0)])
   
    """Step 4: Loop over orders."""
    for order in range(1, max_order+1):
        mirrors.append(list())  # Add per order a list that will contain mirror sources of that order
        
        """Step 5: Loop over sources of this order."""
        for m, mirror in enumerate(mirrors[order-1], start=1):
        
            """Step 6: Loop over walls."""
            for wall in walls:
                
                info_string = "Order: {} - Mirror: {} - Wall: {}".format(order, m, wall)

                """Step 7: Several geometrical truncations. 
                We won't consider a mirror source when..."""
                if wall == mirror.wall:
                    logging.info(info_string + " - Illegal- Generating wall of this mirror.")
                    continue    # ...the (mirror) source one order lower is already at this position.
                
                if mirror.position.on_interior_side_of(wall.plane()) == -1:
                    logging.info(info_string + " - Illegal - Mirror on wrong side of wall. Position: {}".format(mirror.position) )
                    continue    #...the (mirror) source is on the other side of the wall.
                
                if mirror.wall: # Should be mirrored at a wall. This is basically only an issue with zeroth order?
                    #print ('Order: {}'.format(str(order)))
                    #print ('Wall center: {}'.format(str(wall.center)))
                    #print ('Wall plane: {}'.format(str(wall)))
                    #print ('Mirror plane: {}'.format(str(mirror.wall)))
                    #print ('Mirror position: {}'.format(str(mirror.position)))
                    
                    
                    if not wall.center.in_field_angle(mirror.position, mirror.wall, wall.plane()):
                    #if is_point_in_field_angle(mirror.position, wall.center, mirror.wall, wall) == -1:
                        logging.info(info_string + " - Illegal - Center of wall cannot be seen.")
                        continue    #...the center of the wall is not visible from the (mirror) source.
                    #else:
                    
                """Step 8: Evaluate new mirror source and its parameters."""
                position = mirror.position.mirror_with(wall.plane())   # Position of the new source
                
                logging.info(info_string + " - Storing mirror.")
                
                mirrors[order].append(Mirror(position, mirror, wall, order))
                
                
                #position_receiver_distance = position.distance_to(receiver_position)    # Distance between receiver and the new source
                
                #cos_angle = wall.plane().normal().cosines_with(position.cosines_with(receiver_position))   # Cosine of the angle between the line of sight and the wall normal.
                
                
                #try:
                    #refl = (wall.impedance*cos_angle - 1.0) / (wall.impedance*cos_angle + 1.0)    # Reflection coefficient
                #except ZeroDivisionError:   # If angle of incidence is 90 degrees, then cos_angle is 0.0. With hard reflection this results in a division by zero.
                    #refl = 1.0
                
                #strength = mirror.strength * refl   # Amplitude strength due to current and past reflections
                
                #print("Refl {}".format(refl))
                
                """Step 9: Truncation for weak q."""
                
                ###"""Check if q is not too weak."""                
                ###if np.all(strength < min_amplitude):
                    ###logging.info(info_string + " - Source is too weak: {}".format(strength))
                    ###continue
                ###"""Check if q not too far away."""
                ###if (position_receiver_distance / source_receiver_distance) > max_distance:
                    ###logging.info(info_string + " - Source is too far away: {} > {}".format(position_receiver_distance / source_receiver_distance, max_distance))
                    ###continue
                
                """Check if q can be seen."""
                """We have to create a plane on which the receiver_position is situated."""
                
                #effective = not is_shadowed(mirror.position, receiver_position, walls)
                
                #logging.info(info_string + " - Mirrorsource: {} - Effective: {}".format(position, effective))
                #mirrors[order].append(Mirror(position, mirror, wall, order, position_receiver_distance, strength, effective))

    yield from (val for subl in mirrors for val in subl)


def children(mirrors, mirror):
    """Yield children of mirror.
    """
    for m in mirrors:
        if m.mother == mirror:
            yield m

#def plot_model(model, receiver=0, positions=True, direct=False, intersections=True, filename=None):
    #"""
    #Render of the image source model.
    #"""
    #fig = plt.figure()
    #ax = fig.add_subplot(111, projection='3d')
    #receiver = model.receiver[receiver]
    #ax.scatter(model.receiver.x, model.receiver.y, model.receiver.z, marker='p', c='g')
    #mirrors = list(model.mirrors())
    #for mirror in mirrors: 
        #while True:
            ## Position of mirror
            #if positions:
                #ax.scatter(mirror.position.x, mirror.position.y, mirror.position.z)    
            
            ## Direct (though possibly not effective) path to receiver.
            #if direct:
                #ax.add_artist(Arrow3D.from_points(mirror.position,
                                                    #receiver,
                                                    #mutation_scale=20, 
                                                    #lw=1,
                                                    #arrowstyle="-|>"
                                                    #))
            

                
            
            #if mirror.mother is None:
                #ax.add_artist(Arrow3D.from_points(mirror.position,
                                                    #receiver,
                                                    #mutation_scale=20, 
                                                    #lw=1,
                                                    #arrowstyle="-|>"
                                                    #))
                #break
            #else:
                #if intersections:
                    #intersection = mirror.wall.plane().intersection(mirror.mother.position, mirror.position)
                    #ax.scatter(intersection.x, intersection.y, intersection.z)
                    #ax.add_artist(Arrow3D.from_points(mirror.position,
                                                    #intersection,
                                                    #mutation_scale=20, 
                                                    #lw=1,
                                                    #arrowstyle="-|>"
                                                    #))
                #mirror = mirror.mother
                    
    #return fig
    



def plot_model(model, draw_source=True, draw_receiver=True, draw_mirrors=True, draw_walls=True):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d', aspect='equal')
    
    mirrors = list(model.mirrors())
    
    if draw_receiver:
        receiver = np.asarray(model.receiver).T
        ax.scatter(receiver[0], receiver[1], receiver[2], marker='o', c='g')
        del receiver
    
    if draw_source:
        source = np.asarray(model.source).T
        ax.scatter(source[0], source[1], source[2], marker='x', c='r')
        del source
    
    if draw_mirrors:
        _draw_mirrors(ax, mirrors)
    
    if draw_walls:
        _draw_walls(ax, model.walls)

    return fig

def _draw_mirrors(ax, mirrors):
    for mirror in mirrors:
        if mirror.order!=0:
            ax.scatter(mirror.position.x, mirror.position.y, mirror.position.z, marker='x', c='b') 
    return ax
    

def _draw_walls(ax, walls):
    
    if not walls:
        return ax
    
    ARROW_LENGTH = 10.0
    COLOR_FACES = (0.5, 0.5, 1.0)
    
    polygons = Poly3DCollection( [wall.points for wall in walls], alpha=0.5 )
    polygons.set_facecolor(COLOR_FACES)
    #polygons.tri.set_edgecolor('k')
    
    ax.add_collection3d( polygons )
    
    #arrows = Patch3DCollection( [Arrow3D.from_points(wall.center, wall.center + (wall.plane().normal()*ARROW_LENGTH) ) for wall in walls ] )
    #ax.add_collection3d(arrows)
    
    for wall in walls:
        ax.add_artist(Arrow3D.from_points((wall.center), 
                                          (wall.center + wall.plane().normal()*ARROW_LENGTH), 
                                          mutation_scale=20, 
                                          lw=1,
                                          arrowstyle="-|>"))
    
    
    
    #ax.relim() # Does not support Collections!!! So we have to manually set the view limits...
    #ax.autoscale()#_view()

    coordinates = np.array( [wall.points for wall in walls] ).reshape((-1,3))
    minimum = coordinates.min(axis=0)
    maximum = coordinates.max(axis=0)
    
    ax.set_xlim(minimum[0] - ARROW_LENGTH, maximum[0] + ARROW_LENGTH)
    ax.set_ylim(minimum[1] - ARROW_LENGTH, maximum[1] + ARROW_LENGTH)
    ax.set_zlim(minimum[2] - ARROW_LENGTH, maximum[2] + ARROW_LENGTH)

    ax.set_xlabel(r'$x$ in m')
    ax.set_ylabel(r'$y$ in m')
    ax.set_zlabel(r'$z$ in m')
    
    return ax


def plot_walls(walls, filename=None):
    """
    Render of the walls.
    
    :param walls: Iterable of walls.
    :param filename: Optional filename to write figure to.
    
    :returns: figure if filename not specified else None
    
    """
    
    ARROW_LENGTH = 10.0
    COLOR_FACES = (0.5, 0.5, 1.0)
    
    
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d', aspect='equal')
    #ax = fig.gca(projection='3d')
    ax.set_aspect("equal")
    polygons = Poly3DCollection( [wall.points for wall in walls], alpha=0.5 )
    polygons.set_facecolor(COLOR_FACES)
    #polygons.tri.set_edgecolor('k')
    
    ax.add_collection3d( polygons )
    
    #arrows = Patch3DCollection( [Arrow3D.from_points(wall.center, wall.center + (wall.plane().normal()*ARROW_LENGTH) ) for wall in walls ] )
    #ax.add_collection3d(arrows)
    
    for wall in walls:
        ax.add_artist(Arrow3D.from_points((wall.center), 
                                          (wall.center + wall.plane().normal()*ARROW_LENGTH), 
                                          mutation_scale=20, 
                                          lw=1,
                                          arrowstyle="-|>"))
    
    
    
    #ax.relim() # Does not support Collections!!! So we have to manually set the view limits...
    #ax.autoscale()#_view()

    coordinates = np.array( [wall.points for wall in walls] ).reshape((-1,3))
    minimum = coordinates.min(axis=0)
    maximum = coordinates.max(axis=0)
    
    ax.set_xlim(minimum[0] - ARROW_LENGTH, maximum[0] + ARROW_LENGTH)
    ax.set_ylim(minimum[1] - ARROW_LENGTH, maximum[1] + ARROW_LENGTH)
    ax.set_zlim(minimum[2] - ARROW_LENGTH, maximum[2] + ARROW_LENGTH)

    ax.set_xlabel(r'$x$ in m')
    ax.set_ylabel(r'$y$ in m')
    ax.set_zlabel(r'$z$ in m')

    if filename:
        fig.savefig(filename)
    else:
        return fig
    

###class AnimatedScatter(object):
    ###"""An animated scatter plot using matplotlib.animations.FuncAnimation."""
    ###def __init__(self, data, numpoints=50):
        ###self.numpoints = numpoints
        ###self.data = data
        
        #### Setup the figure and axes...
        ###self.fig, self.ax = plt.subplots()
        #### Then setup FuncAnimation.
        ###self.ani = animation.FuncAnimation(self.fig, self.update, interval=5, 
                                           ###init_func=self.setup_plot, blit=True)

    ###def setup_plot(self):
        ###"""Initial drawing of the scatter plot."""
        ###x, y, s, c = next(self.stream)
        ###self.scat = self.ax.scatter(x, y, c=c, s=s, animated=True)
        ###self.ax.axis([-10, 10, -10, 10])

        #### For FuncAnimation's sake, we need to return the artist we'll be using
        #### Note that it expects a sequence of artists, thus the trailing comma.
        ###return self.scat,

    ###def update(self, i):
        ###"""Update the scatter plot."""
        ###data = next(self.data)

        #### Set x and y data...
        ###self.scat.set_offsets(data[:2, :])
        #### Set sizes...
        ###self.scat._sizes = 300 * abs(data[2])**1.5 + 100
        #### Set colors..
        ###self.scat.set_array(data[3])

        #### We need to return the updated artist for FuncAnimation to draw..
        #### Note that it expects a sequence of artists, thus the trailing comma.
        ###return self.scat,

    ###def show(self):
        ###plt.show()


###def animate_model(model):
    
    ###def _init():
        ###dp.set_data([], [], [])
    
    ###def _animate(i):
        ###receiver = np.asarray(model.receiver).T
        ###dp.set_data(receiver[0], receiver[1], receiver[2], marker='o', c='g')
        ###return dp
    
    ###fig = plt.figure()
    ###ax = fig.add_subplot(111, projection='3d', aspect='equal')
    ###dp = ax.scatter([], [], [])# lw=2)
    
    ###animation.FuncAnimation(fig, _animate, frames=model.determine(), init_func=_init)#, blit=True)

###x = np.linspace(0, 10, 1000)

###def init():
    ###line.set_data([], [])
    ###return line,

###def animate(i):
    ###line.set_data(x, np.cos(i * 0.02 * np.pi) * np.sin(x - i * 0.02 * np.pi))
    ###return line,


