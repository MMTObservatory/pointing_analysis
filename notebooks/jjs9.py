from __future__ import print_function
"""
JS9 wrapper to be used in Jupyter/IPython notebooks

Matias Carrasco Kind
"""
__author__ = 'Matias Carrasco Kind'
import uuid
import json
from astropy import wcs
from astropy.io import fits
import pyjs9
from six import BytesIO
import base64
from socketIO_client import SocketIO
import re
import os

init_js9 = False

def libinit(root='http://localhost:8888/files/'):
    """
    Initialization function needed to load javascript libraries and css styles into the notebook.

    Parameters:
    -----------
    root : root url where main path for the notebook is running
    """
    global init_js9
    init_js9 = True
    #root = 'http://localhost:8888/files/'
    req = """
    require.config({
      paths: {
          js9: '%sjs9-allinone',
      }
    });
    """ % root
    css = """
    <link rel="stylesheet" type="text/css" href="%sjs9-allinone.css">
    """ % root
    init = """
    require(['js9'], function(){
        console.log('Loaded');     
    });
    """
    get_ipython().run_cell_magic('javascript', '', req)
    get_ipython().run_cell_magic('html', '', css)
    get_ipython().run_cell_magic('javascript', '', init)

class Js9Local(object):
    """Jupyter Notebbok wrapper around JS9 class object"""
    def __init__(self, root='http://localhost:8888/files/',do_init=False):
        """
        Initiate the class with an unique id unless is manually parsed

        Parameters:
        -----------
        wid : Id to be use for the JS9 display. Default a unique id is created
        """
        global init_js9
        if not init_js9:
             if do_init:libinit(root=root)
             init_js9 = True

        self.created = False
        self.wid = uuid.uuid4().hex
        self.url = None
        self.wcs = None
        self.header = None
        self.suffix = 'JS9' 

    def DelDiv(self):
        """
        Delete current div for this class
        """
        if self.created:
            self.CloseImage()
            command = """$('#{}').remove();""".format(self.wid)
            get_ipython().run_cell_magic('javascript', '', command)
            self.created = False
            self.wid = uuid.uuid4().hex


    def NewDiv(self, width='100%', height='512px'):
        """
        Creates a new div to be added to the notebook cell

        Parameters:
        -----------

        width :  width of the displayed window in css style (string). Default is 
                 80% of the screen
        height : height of the displayed window in css style (string). Default is 
                 512px of the screen
        
        """
        if self.created:
            self.DelDiv()
        print('Display id = {}JS9'.format(self.wid))
        command = """
        "<div id='{0}' ><div class='JS9Menubar' id='{0}JS9Menubar'></div><div class='JS9' id='{0}JS9'></div></div>"
        """.format(self.wid, width, height)
        js_command = "element.append({});".format(command)
        get_ipython().run_cell_magic('javascript', '', js_command)
        get_ipython().run_cell_magic('javascript', '', "JS9.AddDivs('{}JS9');".format(self.wid))
        self.created = True

    def Load(self, url, **kwargs):
        """
        Loads a FITS file into the display created.
        Parameters:
        -----------
        url : Path to file (can be locally)
        Extra arguments in form of a dictionary used by the JS9 javascript object JS9.Load()
        """
        opts = ''
        self.url = url
        if not 'wcsunits' in kwargs:
            kwargs['wcsunits'] = 'degrees'
        if not 'scaleclipping' in kwargs:
            kwargs['scaleclipping'] = 'zscale'
        if len(kwargs) > 0:
            opts = json.dumps(kwargs)+','
        fmt = dict(url=self.url, kw=opts, wid=self.wid, suffix=self.suffix)
        command = "JS9.Load('{url}',{kw}{{display:'{wid}{suffix}'}});".format(**fmt)
        try:
            hdulist = fits.open(url)
            temp_wcs = wcs.WCS(hdulist[0].header)
            self.header = hdulist[0].header
            self.wcs_world2pix = temp_wcs.wcs_world2pix
            self.wcs_pix2world = temp_wcs.wcs_pix2world
            hdulist.close()
        except:
            pass
        get_ipython().run_cell_magic('javascript', '', command)

    def CloseImage(self):
        """
        Close current image
        """
        command = "JS9.CloseImage({{display:'{wid}{suffix}'}});".format(wid=self.wid, suffix=self.suffix)
        get_ipython().run_cell_magic('javascript', '', command)

    def SetColorMap(self, colormap, contrast=None, bias=None):
        """
        Set color map of currently displayed image

        Parameters:
        -----------

        colormap: colormap name
        contrast: contrast value (range: 0 to 10)
        bias: bias value (range 0 to 1)
        """
        extra = ''
        if contrast is not None:
            extra += '%f,' % contrast
        if bias is not None:
            extra  += '%f,' % bias
        fmt = dict(wid=self.wid,cmap=colormap, extra=extra, suffix=self.suffix)
        command = "JS9.SetColormap('{cmap}', {extra} {{display:'{wid}{suffix}'}});".format(**fmt)
        get_ipython().run_cell_magic('javascript', '', command)
       
    def AddRegions(self, **kwargs):
        """
        Add Regions to JS9 display using same syntax as JS9.AddRegions.
        This uses astropy.wcs to do the coordinates transformations
        """
        # Addregions use pixel coordinates. listRegions and SaveRegions use RA and Dec.
        n_objs = 0
        objs = []
        # default shape is circle
        if not 'shape' in kwargs:
            kwargs['shape'] = ['circle']
        for k in kwargs.keys():
            n_objs = max(n_objs, len(kwargs[k]))
        for j in range(n_objs):
            temp = {}
            for k in kwargs.keys():
                try:
                    temp[k] = kwargs[k][j]
                except IndexError:
                    if k == 'shape': 
                        temp[k] = 'circle'
            objs.append(temp)
        self.all_objs = json.dumps(objs)
        command = "JS9.AddRegions({objs}, {{display:'{wid}{suffix}'}})".format(objs=self.all_objs, wid=self.wid, suffix=self.suffix)
        get_ipython().run_cell_magic('javascript', '', command)

    def RegionList(self):
        """
        Name the JS9 GetShapes object string as RegionList.
        RegionList can be called in python after running Js9Local.RegionList().
        """
        command = """
        IPython.notebook.kernel.execute("RegionList=" + JSON.stringify(JS9.GetShapes("regions", {{display: '{wid}JS9'}})));
        """.format(wid=self.wid)
        get_ipython().run_cell_magic('javascript', '', command)

    def ReadRegions(self, fname="temp"):
        """
        ReadRegions() must be be run before SaveRegions() to save regions.
        Create a default temp file with regions written in one line, which is deleted after SaveRegions().
        IPython.notebook.kernel.execute has a problem with new lines.
        For loop must be in one line for IPython.notebook.kernel.execute.
        """
        self.fname = fname
        command = """IPython.notebook.kernel.execute('file = open("temp", "w"); [file.write(x["wcsstr"]) for x in '+ JSON.stringify(JS9.GetShapes("regions", {{display: '{wid}JS9'}})) +']; file.close()');""".format(wid=self.wid)
        get_ipython().run_cell_magic('javascript', '', command)

    def SaveRegions(self, fname="js9.reg"):
        """
        Save regions to a text file in the directory of the running Jupyter notebook
        following JS9 SaveRegions format with header and each region starts with a new line.
        Default file name is js9.reg. Users can specifiy their own file name.
        """
        self.fname = fname
        temp = open('temp','r').read()
        regions = re.sub(r'(circle)', r'\n\1', temp)
        regions = "# Region file format: JS9 version 1.0\nICRS"+regions
        file = open(fname, "w")
        file.write(regions)
        file.close()
        os.remove("temp")

    def LoadRegions(self, fname='js9.reg'):
        """
        LoadRegions() loads saved regions from a user-specified file in the current Jupyter notebook's directory
        """
        self.fname=fname
        command = "JS9.LoadRegions('{fname}', {{display:'{wid}JS9'}})".format(fname=fname, wid=self.wid)
        get_ipython().run_cell_magic('javascript', '', command)
        

default_root = 'http://141.142.236.170'
default_port_html = 8000
default_port_io = 8001
default_width = 970
default_height= 600

def NewDiv(width=default_width, height=default_height):
    """
    Creates a new div to be added to the notebook cell
    The name 'NewDiv' is temporary. 
    
    Parameters:
    -----------
    width :  width of the displayed window in css style (string). Default is 970.
    height : height of the displayed window in css style (string). Default is 600.
    -----------
    examples:
    >>> import jjs9
    >>> jjs9.NewDiv()    
    """

    global wid
    wid = uuid.uuid4().hex
    print('Display id = {}JS9'.format(wid))
    fmt = dict(url=default_root, port0=default_port_html, wid=wid, width=width, height=height)
    html_command = """
    <iframe src='{url}:{port0}/{wid}' width='{width}' height='{height}'>
    </iframe>
    """.format(**fmt)
    get_ipython().run_cell_magic('html', '', html_command)


class Js9Server(pyjs9.JS9):
    """
    Connect to server that runs js9Helper.js for server-side analysis
    Js9Server is best for Jupyter notebook running on a local computer. 
    Analyses are done by communicating with the JS9 back-end server using socket.io.

    Example:
    >>> J = jjs9.Js9Server()
    >>> J.LoadFITS('filename.fits')

    Note that the name assignment J = jjs9.Js9Server() will only give the name to the latest NewDiv,
    so it's recommended to give a name of a NewDiv immediately after calling NewDiv().

    All pyjs9 functionality are available. https://github.com/ericmandel/pyjs9

    Examples:
    >>> J.LoadProxy('http://hea-www.cfa.harvard.edu/~eric/coma.fits', {'scale':'linear', 'colormap':'sls'})
    >>> J.SetColormap('red')

    """
    
    def __init__(self, root=default_root, port_html=default_port_html, port_io=default_port_io):
        self.wcs = None
        self.header = None
        self.root = root
        self.port_html = port_html
        self.port_io = port_io
        super(Js9Server, self).__init__(host=root+':'+str(port_io),id=wid+'JS9')

    def LoadFITS(self, name=None):
        """
        Load('filename') from pyjs9 opens files on the JS9 website server.
        LoadFITS('filename.fits') opens fits files local to the user's running jupyter notebook.
        LoadFITS and SetFITS use a similar algorithm.
        """
        F=fits.open(name)
        # in-memory string	
        memstr=BytesIO()
        # write fits to memory string
        F.writeto(memstr)
        # get memory string as an encoded string
        encstr = base64.b64encode(memstr.getvalue())
        # set up JS9 options
        opts = {}
        if name:
            opts['filename'] = name
        # send encoded file to JS9 for display
        got = self.Load(encstr, opts)
        # finished with memory string
        memstr.close()
        return got
        
