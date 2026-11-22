"""Read-only physical allocation from the existing R51c audit."""
import ctypes

def disk_allocation(path):
    """FileStandardInfo allocation, distinct from uncompressed file length."""
    class Standard(ctypes.Structure):
        _fields_ = [('allocation', ctypes.c_longlong), ('end', ctypes.c_longlong),
                    ('links', ctypes.c_ulong), ('delete_pending', ctypes.c_ubyte),
                    ('directory', ctypes.c_ubyte)]
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.CreateFileW.argtypes = (ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p,
                             ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p)
    k.CreateFileW.restype = ctypes.c_void_p
    k.GetFileInformationByHandleEx.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong)
    k.CloseHandle.argtypes = (ctypes.c_void_p,)
    h = k.CreateFileW(str(path), 0, 7, None, 3, 0, None)
    if h == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        info = Standard()
        if not k.GetFileInformationByHandleEx(h, 1, ctypes.byref(info), ctypes.sizeof(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        return {'allocated_bytes': info.allocation, 'logical_bytes': info.end, 'hard_links': info.links}
    finally:
        k.CloseHandle(h)

