// demo/DemoFlasher.Native/app.cpp
#include <windows.h>
#include "flashcore.h"
enum { ID_ECU = 1001, ID_PATH, ID_BROWSE, ID_FLASH, ID_STATUS, ID_NORESP };
static HWND hEcu, hPath, hStatus, hNoResp;

static LRESULT CALLBACK WndProc(HWND h, UINT m, WPARAM w, LPARAM l) {
    switch (m) {
    case WM_CREATE: {
        HINSTANCE hi = ((LPCREATESTRUCT)l)->hInstance;
        hEcu = CreateWindowW(L"COMBOBOX", L"", WS_CHILD | WS_VISIBLE | CBS_DROPDOWNLIST | WS_TABSTOP, 20, 20, 200, 120, h, (HMENU)ID_ECU, hi, 0);
        const wchar_t* ecus[] = { L"ECU1", L"ECU2", L"Gateway" };
        for (const wchar_t* s : ecus) SendMessageW(hEcu, CB_ADDSTRING, 0, (LPARAM)s);
        hPath = CreateWindowW(L"EDIT", L"", WS_CHILD | WS_VISIBLE | WS_BORDER | ES_AUTOHSCROLL, 20, 56, 300, 24, h, (HMENU)ID_PATH, hi, 0);
        CreateWindowW(L"BUTTON", L"Browse...", WS_CHILD | WS_VISIBLE, 330, 55, 90, 26, h, (HMENU)ID_BROWSE, hi, 0);
        CreateWindowW(L"BUTTON", L"Flash", WS_CHILD | WS_VISIBLE, 20, 92, 100, 30, h, (HMENU)ID_FLASH, hi, 0);
        hNoResp = CreateWindowW(L"BUTTON", L"Simulate no response", WS_CHILD | WS_VISIBLE | BS_AUTOCHECKBOX, 250, 96, 180, 24, h, (HMENU)ID_NORESP, hi, 0);
        hStatus = CreateWindowW(L"STATIC", L"Ready", WS_CHILD | WS_VISIBLE, 20, 162, 400, 22, h, (HMENU)ID_STATUS, hi, 0);
        return 0; }
    case WM_COMMAND:
        if (LOWORD(w) == ID_BROWSE) {
            wchar_t file[MAX_PATH] = L"";
            OPENFILENAMEW ofn = { sizeof ofn }; ofn.hwndOwner = h; ofn.lpstrFile = file; ofn.nMaxFile = MAX_PATH;
            ofn.lpstrTitle = L"Open"; ofn.Flags = OFN_FILEMUSTEXIST;
            if (GetOpenFileNameW(&ofn)) SetWindowTextW(hPath, file);
        } else if (LOWORD(w) == ID_FLASH) {
            char path[MAX_PATH]; GetWindowTextA(hPath, path, MAX_PATH);
            int ecu = (int)SendMessageW(hEcu, CB_GETCURSEL, 0, 0);
            SetWindowTextW(hStatus, L"Flashing...");
            if (SendMessageW(hNoResp, BM_GETCHECK, 0, 0) == BST_CHECKED) {
                SetWindowTextW(hStatus, L"Error");
                MessageBoxW(h, L"Error: ECU not responding", L"DemoFlasherNative", MB_OK | MB_ICONERROR);
            } else if (Flash(path, ecu) == 0) SetWindowTextW(hStatus, L"Done: flashed");
            else { SetWindowTextW(hStatus, L"Error"); MessageBoxW(h, L"Error: no ECU or file", L"DemoFlasherNative", MB_OK | MB_ICONERROR); }
        }
        return 0;
    case WM_DESTROY: PostQuitMessage(0); return 0;
    }
    return DefWindowProcW(h, m, w, l);
}

int WINAPI wWinMain(HINSTANCE hi, HINSTANCE, PWSTR, int show) {
    WNDCLASSW wc = {}; wc.lpfnWndProc = WndProc; wc.hInstance = hi; wc.lpszClassName = L"DemoFlasherNative";
    wc.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1); wc.hCursor = LoadCursor(0, IDC_ARROW);
    RegisterClassW(&wc);
    HWND h = CreateWindowW(L"DemoFlasherNative", L"DemoFlasherNative", WS_OVERLAPPEDWINDOW & ~WS_THICKFRAME,
                           CW_USEDEFAULT, CW_USEDEFAULT, 460, 240, 0, 0, hi, 0);
    ShowWindow(h, show);
    MSG msg; while (GetMessageW(&msg, 0, 0, 0)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
    return 0;
}
