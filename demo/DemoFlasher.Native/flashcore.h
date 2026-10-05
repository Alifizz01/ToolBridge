// demo/DemoFlasher.Native/flashcore.h
#pragma once
#ifdef FLASHCORE_EXPORTS
#define FC_API __declspec(dllexport)
#else
#define FC_API __declspec(dllimport)
#endif
FC_API int Flash(const char* path, int ecu);
FC_API int EraseAll(int ecu);
FC_API const char* Version();
