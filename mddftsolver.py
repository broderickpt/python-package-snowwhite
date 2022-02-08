
from snowwhite import *
import numpy as np

try:
    import cupy as cp
except ModuleNotFoundError:
    cp = None


class MddftProblem(SWProblem):
    """Define Multi-dimention DFT problem."""

    def __init__(self, ns, k=SW_FORWARD):
        """Setup problem specifics for MDDFT solver.
        
        Arguments:
        ns     -- dimensions of MDDFT
        """
        super(MddftProblem, self).__init__()
        self._ns = ns
        self._k = k
        
    def dimensions(self):
        return self._ns
        
    def direction(self):
        return self._k
        

class MddftSolver(SWSolver):
    def __init__(self, problem: MddftProblem, opts = {}):
        if not isinstance(problem, MddftProblem):
            raise TypeError("problem must be an MddftProblem")
        
        typ = 'z'
        if opts.get(SW_OPT_REALCTYPE, 0) == 'float':
            typ = 'c'
        ns = 'x'.join([str(n) for n in problem.dimensions()])
        namebase = ''
        if problem.direction() == SW_FORWARD:
            namebase = typ + 'mddft_fwd_' + ns
        else:
            namebase = typ + 'mddft_inv_' + ns
        
        if opts.get(SW_OPT_COLMAJOR, False):
            namebase = namebase + '_F'
                    
        super(MddftSolver, self).__init__(problem, namebase, opts)

    def runDef(self, src):
        """Solve using internal Python definition."""
        
        xp = get_array_module(src)

        if self._problem.direction() == SW_FORWARD:
            FFT = xp.fft.fftn ( src )
        else:
            FFT = xp.fft.ifftn ( src ) 

        return FFT
        
    def _trace(self):
        pass

    def solve(self, src):
        """Call SPIRAL-generated function."""
        
        xp = get_array_module(src)

        nt = tuple(self._problem.dimensions())
        ordc = 'F' if self._colMajor else 'C'
        dst = xp.zeros(nt, src.dtype,  order=ordc)
        self._func(dst, src)
        if self._problem.direction() == SW_INVERSE:
            xp.divide(dst, xp.size(dst), out=dst)
        return dst

    def _writeScript(self, script_file):
        filename = self._namebase
        nameroot = self._namebase
        dims = str(self._problem.dimensions())
        filetype = '.c'
        if self._genCuda:
            nameroot = nameroot + '_cu'
            filetype = '.cu'
        
        print("Load(fftx);", file = script_file)
        print("ImportAll(fftx);", file = script_file) 
        if self._genCuda:
            print("conf := LocalConfig.fftx.confGPU();", file = script_file) 
        else:
            print("conf := LocalConfig.fftx.defaultConf();", file = script_file) 
        print("t := let(ns := " + dims + ",", file = script_file) 
        print('    name := "' + nameroot + '",', file = script_file)
        # -1 is inverse for Numpy and forward (1) for Spiral
        if self._colMajor:
            print("    TFCall(TRC(TColMajor(MDDFT(ns, " + str(self._problem.direction() * -1) + "))), rec(fname := name, params := []))", file = script_file)
        else:
            print("    TFCall(TRC(MDDFT(ns, " + str(self._problem.direction() * -1) + ")), rec(fname := name, params := []))", file = script_file)
        print(");", file = script_file)        

        print("opts := conf.getOpts(t);", file = script_file)
        if self._opts.get(SW_OPT_REALCTYPE) == "float":
            print('opts.TRealCtype := "float";', file = script_file)
        print("tt := opts.tagIt(t);", file = script_file)
        print("", file = script_file)
        print("c := opts.fftxGen(tt);", file = script_file)
        print('PrintTo("' + filename + filetype + '", opts.prettyPrint(c));', file = script_file)
        print("", file = script_file)
        
    def _writeCudaHost(self):
        """ Write CUDA host code """
        
        # Python interface to C libraries does not handle mangled names from CUDA/C++ compiler
        
        typ = 'double'
        if self._opts.get(SW_OPT_REALCTYPE, 0) == 'float':
            typ = 'float'
        
        dims = tuple(self._problem.dimensions())
        
        inSzStr  = str(2 * np.prod(dims))
        outSzStr = str(2 * np.prod(dims))
        
        cu_hostFileName = self._namebase + '_host.cu'
        cu_hostFile = open(cu_hostFileName, 'w')
        
        genby = 'Host-to-Device C/CUDA Wrapper generated by ' + self.__class__.__name__
        print('/*', file=cu_hostFile)
        print(' * ' + genby, file=cu_hostFile)
        print(' */', file=cu_hostFile)
        print('', file=cu_hostFile)
        
        print('#include <helper_cuda.h> \n', file=cu_hostFile)
        
        print('extern void init_' + self._namebase + '_cu();', file=cu_hostFile)
        
        print('extern void ' + self._namebase + '_cu' + '(' + typ + '  *Y, ' + typ + '  *X);', file=cu_hostFile)
        print('extern void destroy_' + self._namebase + '_cu();\n', file=cu_hostFile)
        print('extern "C" { \n', file=cu_hostFile)
        print('void init_' + self._namebase + '()' + '{', file=cu_hostFile)
        
        print('    init_' + self._namebase + '_cu();', file=cu_hostFile)
        print('} \n', file=cu_hostFile)
        
        print('void ' + self._namebase + '(' + typ + '  *Y, ' + typ + '  *X) {', file=cu_hostFile)
        print('    ' + self._namebase + '_cu(Y, X);', file=cu_hostFile)
        print('    checkCudaErrors(cudaGetLastError());', file=cu_hostFile)
        print('} \n', file=cu_hostFile)
        
        print('void destroy_' + self._namebase + '() {', file=cu_hostFile)
        print('    destroy_' + self._namebase + '_cu();', file=cu_hostFile)
        print('} \n', file=cu_hostFile)
        print('}', file=cu_hostFile)
        
        cu_hostFile.close()







