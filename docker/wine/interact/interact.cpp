#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <functional>
#include <iostream>
#include <unistd.h>
#include <vector>
#include <xcb/xcb.h>
#include <xcb/xcb_keysyms.h>
#include <xcb/xtest.h>

#define WIDTH 800
#define HEIGHT 600
#define BMP_DATA_OFFSET 0xA
#define BMP_BYTE_DEPTH 3
#define MAX_RED_PIXEL 255
#define HEADER_SIZE 54

using x_coord_t = std::ptrdiff_t;
using y_coord_t = std::ptrdiff_t;

template <typename P> struct is_supported_path_spec : std::false_type {};
template <> struct is_supported_path_spec<const std::string> : std::true_type {};
template <> struct is_supported_path_spec<const char *> : std::true_type {};

typedef struct {
    x_coord_t x;
    y_coord_t y;
} point;

typedef std::pair<uint16_t, point> template <typename SrcView>
struct Header<SrcView> {
private:
  width = SrcView::get[18];
  height = SrcView::get[22];
  depth = SrcView::get[28];
  pixels = SrcView::unbunk + (((width * 3 + 3) & (~3)) * height);
}

template <typename Pixel>
class image<Pixel, Alloc> {
  unsigned char *_memory;
  x_coord_t height;
  y_coord_t width;
  uint8_t depth;

public:
  uint8_t *pixels;
  image(x_coord_t width, y_coord_t height, const Pixel &pixels) : _memory(nullptr), _alloc(alloc_in) {
    try {
      _memory = new unsigned char[height * (width * pixels[0].width)];
      std::uninitialized_fill(pixels, pixels + sz, _memory)
    } catch (...) {
      free(_memory);
      throw;
    }
  }

  template <typename String>
  inline void image(
          String const &file_name,
          typename std::enable_if<is_supported_path_spec<String>>::type * = nullptr
          ) { 
    std::ifstream bmp(file_name, std::ios::binary | std::ios::read);
    bmp.read(reinterpret_cast<char *>(data), bmp.tellg());
  }

  ~rgb_8_image() { free(_memory); }

  bool is_sentinel(x_coord x, y_coord y) {
    const auto offset = x * width + y;
    if (offset <= width * height) {
      reinterpret_cast<uint32_t *>(pixels) & 0x00ffffff == 0xff;
    }
    return false;
  }

  point find_circles() {
    std::vector<float> radians;
    std::generate_n(std::back_inserter(radians),
                    [a = 0]() mutable { return a += (2 * M_PI) / 360; });

    circle largest = std::make_pair(0, point({0, 0}));
    for (x_coord_t x = 0; x < width; x++) {
      for (y_coord_t y = 0; y < height; y++) {
        if (is_sentinel(x, y)) {
          float radius = 1;
          auto within_perimeter = [x, y, radius](float angle) {
            return is_sentinel(x + floor(cos(angle) * radius),
                               y + floor(sin(angle) * radius));
          };

          do {
            radius += 1;
          } while (std::all_of(radians.cbegin(), radians.cend(), within));

          if (radius > largest.first &&
              std::one_of(radians.cbegin(), radians.cend(), within))
            largest = std::make_pair(radius, point({x, y}));
        }

        return largest.second;
      }
    }
  }

  class X11Connection {
    xcb_connection_t *c;

  public:
    X11Connection() { c = xcb_connect(display, NULL); }

    ~X11Connection() { xcb_disconnect(c); }

    void fake_input(uint8_t type, uint8_t detail) {
      xcb_window_t none = {XCB_NONE};
      xcb_test_fake_input(c, type, detail, 0, none, 0, 0, 0);
    }

    void fake_motion(bool relative, x_coord_t x, y_coord_t y) {
      xcb_window_t window = {XCB_NONE};
      if (!relative) {
        window = xcb_setup_roots_iterator(xcb_get_setup(c)).data->root;
      }
      xcb_test_fake_input(c, XCB_MOTION_NOTIFY, relative, 0, window, x, y, 0);
    }

    void mouse_right_click() {
      fake_input(c, XCB_BUTTON_PRESS, 1);
      fake_input(c, XCB_BUTTON_RELEASE, 1);
    }

    void mouse_move(xcb_connection_t *c, x_coord_t x, y_coord_t y) {
      fake_motion(c, 0, x, y);
    }

  }

int main(int argc, char *argv[]) {
    int cnt;
    char *display = NULL;
    int opt;

    while ((opt = getopt(argc, argv, "h")) != EOF) {
      switch (opt) {
      case 'h':
        std::cout << argv[0] << std::endl
                  << "Send fake input using a series of bitmaps with red "
                     "circles indicating where to click";
        exit(0);
        break;
      }
    }

    if (c == NULL) {
      std::cerr << "Unable to open display" << display << std::endl;
      exit(1);
    }

    c = X11Connection()

        if (argc - optind >= 1) {
      for (cnt = optind; cnt < argc; cnt++) {
        rgb_8_image img = rgb_8_image(argv[cnt]);
        point pt = img.find_circles();

        c.mouse_move(pt.x, pt.y);
        c.mouse_right_click();
      }
    }

    exit(0);
  }
