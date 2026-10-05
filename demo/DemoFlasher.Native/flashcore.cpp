// demo/DemoFlasher.Native/flashcore.cpp
#define FLASHCORE_EXPORTS
#include "flashcore.h"
#include <windows.h>
FC_API int Flash(const char* path, int ecu) {
    if (!path || !*path || ecu < 0) return -1;
    Sleep(1500);
    return 0;
}
FC_API int EraseAll(int) { return 0; }
FC_API const char* Version() { return "1.0"; }
