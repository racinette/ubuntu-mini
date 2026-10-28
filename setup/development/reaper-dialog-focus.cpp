// Read native SWELL keyboard focus even while a modal dialog pauses ReaScript.
// No input injection or window changes; the existing Python helper draws.
// Linux ABI declarations below follow Cockos' reaper_plugin.h (0x20e) and
// WDL/swell/swell-functions.h + swell-types.h. No SDK download is needed to build.
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
#include <limits.h>
#include <string>
#include <unistd.h>

namespace {
using Window = void*;
struct Rect { int left, top, right, bottom; };
using TimerProc = void (*)(Window, unsigned, uintptr_t, unsigned);
struct PluginInfo {
  int version;
  Window main;
  int (*reg)(const char*, void*);
  void* (*get)(const char*);
};
Window (*get_focus)();
Window (*get_parent)(Window);
bool (*visible)(Window);
bool (*get_rect)(Window, Rect*);
void* (*os_window)(Window, const char*);
uintptr_t (*set_timer)(Window, uintptr_t, unsigned, TimerProc);
int (*kill_timer)(Window, uintptr_t);
unsigned long (*xid)(void*);
const char* (*ext_state)(const char*, const char*);
void *swell_handle, *gdk_handle;
uintptr_t timer;
std::string path;

void tick(Window, unsigned, uintptr_t, unsigned) {
  const char* requested = ext_state("device-gamepad", "focus-path");
  if (path != requested) {
    if (!path.empty()) unlink(path.c_str());
    path = requested;
  }
  if (path.empty()) return;
  // All SWELL calls run on its GUI timer thread. Never retain a widget handle
  // between callbacks: dialogs and controls can be destroyed at any moment.
  Window focus = get_focus(), top = focus;
  Rect rect{};
  void* native = nullptr;
  bool valid = focus && visible(focus) && get_rect(focus, &rect);
  for (int depth = 0; valid && top && depth < 64; ++depth) {
    native = os_window(top, "GdkWindow");
    if (native) break; // Stop before an owned dialog's owner (GetParent includes it).
    top = get_parent(top);
  }
  valid = valid && native && focus != top;
  // Clip to each ancestor, so scrolled/partly hidden controls cannot draw over
  // neighboring controls or outside the dialog. Unknown geometry hides it.
  Window current = focus;
  for (int depth = 0; valid && current != top && depth < 64; ++depth) {
    current = get_parent(current);
    Rect bounds{};
    valid = current && visible(current) && get_rect(current, &bounds);
    if (valid) {
      rect.left = std::max(rect.left, bounds.left);
      rect.top = std::max(rect.top, bounds.top);
      rect.right = std::min(rect.right, bounds.right);
      rect.bottom = std::min(rect.bottom, bounds.bottom);
    }
  }
  valid = valid && current == top && rect.right > rect.left && rect.bottom > rect.top;
  const std::string temporary = path + ".tmp";
  if (FILE* file = fopen(temporary.c_str(), "w")) {
    if (valid) fprintf(file, "%lu %d %d %d %d\n", xid(native), rect.left, rect.top,
                       rect.right - rect.left, rect.bottom - rect.top);
    const bool ok = fclose(file) == 0;
    if (ok) rename(temporary.c_str(), path.c_str());
    else unlink(temporary.c_str());
  }
}

void cleanup() {
  if (timer) kill_timer(nullptr, timer);
  timer = 0;
  if (!path.empty()) { unlink(path.c_str()); unlink((path + ".tmp").c_str()); }
  path.clear();
  if (gdk_handle) dlclose(gdk_handle);
  if (swell_handle) dlclose(swell_handle);
  gdk_handle = swell_handle = nullptr;
}
}

extern "C" int ReaperPluginEntry(void*, PluginInfo* info) {
  if (!info) { cleanup(); return 0; }
  if (info->version != 0x20e || !info->get) return 0;
  ext_state = reinterpret_cast<decltype(ext_state)>(info->get("GetExtState"));
  char executable[PATH_MAX];
  const auto length = readlink("/proc/self/exe", executable, sizeof(executable) - 1);
  if (!ext_state || length <= 0) return 0;
  executable[length] = 0;
  char* slash = strrchr(executable, '/');
  if (!slash) return 0;
  const std::string library = std::string(executable, slash + 1) + "libSwell.so";
  swell_handle = dlopen(library.c_str(), RTLD_NOW | RTLD_NOLOAD);
  auto get = swell_handle ? reinterpret_cast<void* (*)(const char*)>(dlsym(swell_handle, "SWELLAPI_GetFunc")) : nullptr;
  if (!get) { cleanup(); return 0; }
#define LOAD(name, symbol) name = reinterpret_cast<decltype(name)>(get(symbol)); if (!name) { cleanup(); return 0; }
  LOAD(get_focus, "GetFocus")
  LOAD(get_parent, "GetParent")
  LOAD(visible, "IsWindowVisible")
  LOAD(get_rect, "GetWindowRect")
  LOAD(os_window, "SWELL_GetOSWindow")
  LOAD(set_timer, "SetTimer")
  LOAD(kill_timer, "KillTimer")
#undef LOAD
  // SWELL loads GDK locally; resolve the already-loaded backend, never load a
  // second GTK/GDK version into REAPER. This device uses Xwayland.
  for (const char* name : {"libgdk-3.so.0", "libgdk-x11-2.0.so.0"}) {
    gdk_handle = dlopen(name, RTLD_NOW | RTLD_NOLOAD);
    if (gdk_handle) {
      xid = reinterpret_cast<decltype(xid)>(dlsym(gdk_handle, "gdk_x11_window_get_xid"));
      if (!xid) xid = reinterpret_cast<decltype(xid)>(dlsym(gdk_handle, "gdk_x11_drawable_get_xid"));
      if (xid) break;
      dlclose(gdk_handle); gdk_handle = nullptr;
    }
  }
  if (!xid) { cleanup(); return 0; }
  timer = set_timer(nullptr, 0, 100, tick);
  if (!timer) { cleanup(); return 0; }
  return 1;
}
