#include "input-method-unstable-v2-client-protocol.h"
#include "state.hpp"
#include "virtual-keyboard-unstable-v1-client-protocol.h"
#include <QCommandLineParser>
#include <QCoreApplication>
#include <QDir>
#include <QElapsedTimer>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLocalServer>
#include <QLocalSocket>
#include <QPointer>
#include <QProcess>
#include <QSet>
#include <QSocketNotifier>
#include <QStandardPaths>
#include <QTimer>
#include <algorithm>
#include <cstring>
#include <fcntl.h>
#include <linux/memfd.h>
#include <memory>
#include <rime_api.h>
#include <sys/file.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <wayland-client.h>
#include <xkbcommon/xkbcommon.h>

class Backend {
public:
  InputState state;
  wl_display *display = nullptr;
  wl_registry *registry = nullptr;
  wl_seat *seat = nullptr;
  zwp_input_method_manager_v2 *manager = nullptr;
  zwp_virtual_keyboard_manager_v1 *vkManager = nullptr;
  zwp_input_method_v2 *im = nullptr;
  zwp_virtual_keyboard_v1 *vk = nullptr;
  QLocalServer server;
  QSet<QLocalSocket *> clients;
  QHash<QLocalSocket *, QByteArray> buffers;
  std::unique_ptr<QSocketNotifier> notifier;
  bool unavailable = false, available = false, manual = false, probe = false,
       rimeReady = false;
  QString language = "en_US", socketPath, rimeData, seatName;
  QString gestureDecoder;
  QPointer<QProcess> decoder;
  bool gestureResult = false;
  uint64_t contextGeneration = 0;
  QStringList dictionary;
  QString prefix;
  bool prediction = true;
  RimeApi *rime = nullptr;
  RimeSessionId session = 0;
  QByteArray userData, sharedData;
  QString preedit;
  QJsonArray candidates;
  int page = 0;
  bool more = false;
  xkb_context *xkb = nullptr;
  xkb_keymap *keymap = nullptr;
  QElapsedTimer clock;
  int lockFd = -1;
  uint32_t wantedSeat = 0;
  Backend() { clock.start(); }
  ~Backend() {
    if (session)
      rime->destroy_session(session);
    if (rimeReady)
      rime->finalize();
    if (keymap)
      xkb_keymap_unref(keymap);
    if (xkb)
      xkb_context_unref(xkb);
    if (vk)
      zwp_virtual_keyboard_v1_destroy(vk);
    if (im)
      zwp_input_method_v2_destroy(im);
    if (display) {
      wl_display_flush(display);
      wl_display_disconnect(display);
    }
    if (lockFd >= 0)
      close(lockFd);
  }
  void flush() {
    if (wl_display_flush(display) < 0 && errno != EAGAIN)
      QCoreApplication::exit(1);
  }
  void reset() {
    ++contextGeneration;
    gestureResult = false;
    if (decoder)
      decoder->kill();
    if (session)
      rime->clear_composition(session);
    preedit.clear();
    candidates = {};
    page = 0;
    more = false;
    prefix.clear();
  }
  bool secure() const { return !state.current.active || state.secure(); }
  QJsonObject status() {
    return {{"type", "state"},
            {"active", state.current.active},
            {"available", available},
            {"secure", secure()},
            {"manual", manual},
            {"inputAllowed", available && (state.current.active || manual)},
            {"gestureAvailable",
             !gestureDecoder.isEmpty() || !dictionary.isEmpty()},
            {"purpose", int(state.current.purpose)},
            {"language", language},
            {"preedit", secure() ? QString() : preedit},
            {"candidates", secure() ? QJsonArray() : candidates},
            {"page", page},
            {"hasMore", more},
            {"serial", qint64(state.serial)},
            {"rimeReady", rimeReady}};
  }
  void send(QLocalSocket *s, QJsonObject obj) {
    if (s->bytesToWrite() > 65536) {
      s->disconnectFromServer();
      return;
    }
    s->write(QJsonDocument(obj).toJson(QJsonDocument::Compact) + '\n');
  }
  void publish() {
    for (auto *s : clients)
      send(s, status());
  }
  void error(QLocalSocket *s, const char *code) {
    send(s, {{"type", "error"}, {"code", code}});
  }
  bool connectWayland() {
    display = wl_display_connect(nullptr);
    if (!display)
      return false;
    registry = wl_display_get_registry(display);
    static const wl_registry_listener listener = {
        [](void *data, wl_registry *r, uint32_t name, const char *iface,
           uint32_t) {
          auto *b = (Backend *)data;
          if (!strcmp(iface, "zwp_input_method_manager_v2"))
            b->manager = (zwp_input_method_manager_v2 *)wl_registry_bind(
                r, name, &zwp_input_method_manager_v2_interface, 1);
          if (!strcmp(iface, "zwp_virtual_keyboard_manager_v1"))
            b->vkManager = (zwp_virtual_keyboard_manager_v1 *)wl_registry_bind(
                r, name, &zwp_virtual_keyboard_manager_v1_interface, 1);
          if (!strcmp(iface, "wl_seat") && !b->seat) {
            b->wantedSeat = name;
            b->seat =
                (wl_seat *)wl_registry_bind(r, name, &wl_seat_interface, 1);
          }
        },
        [](void *data, wl_registry *, uint32_t name) {
          auto *b = (Backend *)data;
          if (name == b->wantedSeat)
            QCoreApplication::exit(1);
        }};
    wl_registry_add_listener(registry, &listener, this);
    if (wl_display_roundtrip(display) < 0)
      return false;
    if (probe)
      return true;
    if (!manager || !vkManager || !seat)
      return false;
    im = zwp_input_method_manager_v2_get_input_method(manager, seat);
    static const zwp_input_method_v2_listener events = {
        [](void *d, zwp_input_method_v2 *) {
          auto *b = (Backend *)d;
          b->state.activate();
        },
        [](void *d, zwp_input_method_v2 *) {
          auto *b = (Backend *)d;
          b->state.deactivate();
        },
        [](void *d, zwp_input_method_v2 *, const char *t, uint32_t c,
           uint32_t a) {
          auto *b = (Backend *)d;
          b->state.pending.surrounding = t;
          b->state.pending.cursor = c;
          b->state.pending.anchor = a;
        },
        [](void *d, zwp_input_method_v2 *, uint32_t cause) {
          if (cause == 1)
            static_cast<Backend *>(d)->state.resetPending = true;
        },
        [](void *d, zwp_input_method_v2 *, uint32_t h, uint32_t p) {
          auto *b = (Backend *)d;
          b->state.pending.hints = h;
          b->state.pending.purpose = p;
        },
        [](void *d, zwp_input_method_v2 *) {
          auto *b = (Backend *)d;
          bool reset = b->state.done();
          if (reset || b->secure()) {
            bool hadPreedit = !b->preedit.isEmpty();
            b->reset();
            if (hadPreedit && b->state.current.active) {
              zwp_input_method_v2_set_preedit_string(b->im, "", 0, 0);
              zwp_input_method_v2_commit(b->im, b->state.serial);
              b->flush();
            }
          }
          if (b->language == "en_US")
            b->updateEnglish();
          b->publish();
        },
        [](void *d, zwp_input_method_v2 *) {
          auto *b = (Backend *)d;
          b->unavailable = true;
          b->available = false;
          b->reset();
          b->publish();
          QCoreApplication::exit(3);
        }};
    zwp_input_method_v2_add_listener(im, &events, this);
    vk = zwp_virtual_keyboard_manager_v1_create_virtual_keyboard(vkManager,
                                                                 seat);
    xkb = xkb_context_new(XKB_CONTEXT_NO_FLAGS);
    if (!xkb)
      return false;
    xkb_rule_names names{};
    names.layout = "us";
    keymap =
        xkb_keymap_new_from_names(xkb, &names, XKB_KEYMAP_COMPILE_NO_FLAGS);
    if (!keymap)
      return false;
    if (!sendKeymap(keymap))
      return false;
    available = true;
    if (wl_display_roundtrip(display) < 0 || !available)
      return false;
    notifier = std::make_unique<QSocketNotifier>(wl_display_get_fd(display),
                                                 QSocketNotifier::Read);
    QObject::connect(notifier.get(), &QSocketNotifier::activated, [this] {
      if (wl_display_dispatch(display) < 0)
        QCoreApplication::exit(1);
      flush();
    });
    return true;
  }
  bool sendKeymap(xkb_keymap *map) {
    char *text = xkb_keymap_get_as_string(map, XKB_KEYMAP_FORMAT_TEXT_V1);
    if (!text)
      return false;
    int fd = syscall(SYS_memfd_create, "hp-os-keymap", MFD_CLOEXEC);
    size_t size = strlen(text) + 1;
    bool ok = fd >= 0 && write(fd, text, size) == ssize_t(size);
    free(text);
    if (!ok) {
      if (fd >= 0)
        close(fd);
      return false;
    }
    zwp_virtual_keyboard_v1_keymap(vk, WL_KEYBOARD_KEYMAP_FORMAT_XKB_V1, fd,
                                   size);
    close(fd);
    flush();
    return true;
  }
  void modifiers(uint32_t mask) {
    zwp_virtual_keyboard_v1_modifiers(vk, mask, 0, 0, 0);
  }
  void rawCode(uint32_t code, uint32_t mods) {
    modifiers(mods);
    uint32_t t = clock.elapsed();
    zwp_virtual_keyboard_v1_key(vk, t, code, WL_KEYBOARD_KEY_STATE_PRESSED);
    zwp_virtual_keyboard_v1_key(vk, t, code, WL_KEYBOARD_KEY_STATE_RELEASED);
    modifiers(0);
    flush();
  }
  bool rawSymbol(xkb_keysym_t symbol, const QJsonArray &mods = {}) {
    uint32_t mask = 0;
    for (auto v : mods) {
      QString n = v.toString();
      const char *m = n == "Control" ? XKB_MOD_NAME_CTRL
                      : n == "Shift" ? XKB_MOD_NAME_SHIFT
                      : n == "Alt"   ? XKB_MOD_NAME_ALT
                      : n == "Super" ? XKB_MOD_NAME_LOGO
                                     : nullptr;
      if (!m)
        return false;
      auto i = xkb_keymap_mod_get_index(keymap, m);
      if (i != XKB_MOD_INVALID)
        mask |= 1u << i;
    }
    for (xkb_keycode_t c = xkb_keymap_min_keycode(keymap);
         c <= xkb_keymap_max_keycode(keymap); ++c) {
      for (xkb_level_index_t level = 0; level < 2; ++level) {
        const xkb_keysym_t *syms;
        int n = xkb_keymap_key_get_syms_by_level(keymap, c, 0, level, &syms);
        for (int i = 0; i < n; ++i)
          if (syms[i] == symbol) {
            uint32_t m = mask;
            if (level)
              m |= 1u << xkb_keymap_mod_get_index(keymap, XKB_MOD_NAME_SHIFT);
            rawCode(c - 8, m);
            return true;
          }
      }
    }
    return false;
  }
  bool rawUnicode(QString text) {
    for (char32_t cp : text.toUcs4()) {
      if (rawSymbol(xkb_utf32_to_keysym(cp)))
        continue;
      // A temporary one-key XKB map gives genuine Unicode key events to clients
      // without text-input. No clipboard, XTest, uinput or synthetic compose
      // trick.
      QByteArray desc =
          QString("xkb_keymap { xkb_keycodes \"hp-os\" { minimum=8; "
                  "maximum=255; <I001>=9; }; xkb_types \"hp-os\" { type "
                  "\"ONE_LEVEL\" { modifiers=None; level_name[Level1]=\"Any\"; "
                  "}; }; xkb_compatibility \"hp-os\" {}; xkb_symbols \"hp-os\" "
                  "{ key <I001> { [ U%1 ] }; }; };")
              .arg(uint(cp), 4, 16, QChar('0'))
              .toUtf8();
      auto *map = xkb_keymap_new_from_string(xkb, desc.constData(),
                                             XKB_KEYMAP_FORMAT_TEXT_V1,
                                             XKB_KEYMAP_COMPILE_NO_FLAGS);
      if (!map)
        return false;
      bool ok = sendKeymap(map);
      xkb_keymap_unref(map);
      if (!ok)
        return false;
      rawCode(1, 0);
      sendKeymap(keymap);
    }
    return true;
  }
  bool commit(QString text) {
    if (!state.current.active)
      return manual && rawUnicode(text);
    QByteArray utf = text.toUtf8();
    zwp_input_method_v2_commit_string(im, utf.constData());
    zwp_input_method_v2_set_preedit_string(im, "", 0, 0);
    zwp_input_method_v2_commit(im, state.serial);
    flush();
    return true;
  }
  bool initRime() {
    if (rimeReady)
      return true;
    if (rimeData.isEmpty())
      return false;
    QString dir =
        QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation) +
        "/hp-os-touch/rime";
    QDir().mkpath(dir);
    chmod(dir.toUtf8().constData(), 0700);
    // Compile only this keyboard's schema; preserve user customizations.
    QFile defaults(dir + "/default.custom.yaml");
    if (!defaults.exists() &&
        defaults.open(QIODevice::WriteOnly | QIODevice::NewOnly))
      defaults.write(
          "patch:\n  schema_list:\n    - schema: luna_pinyin_simp\n");
    defaults.close();
    sharedData = rimeData.toUtf8();
    userData = dir.toUtf8();
    rime = rime_get_api();
    RIME_STRUCT(RimeTraits, traits);
    traits.shared_data_dir = sharedData.constData();
    traits.user_data_dir = userData.constData();
    traits.app_name = "rime.hp-os";
    traits.distribution_name = "HP-OS";
    traits.distribution_code_name = "hp-os";
    traits.distribution_version = "0.1";
    traits.min_log_level = 3;
    traits.log_dir = "";
    rime->setup(&traits);
    rime->initialize(&traits);
    rime->start_maintenance(false);
    rime->join_maintenance_thread();
    if (!rime->deploy_schema(
            (rimeData + "/luna_pinyin_simp.schema.yaml").toUtf8().constData()))
      return false;
    session = rime->create_session();
    if (!session)
      return false;
    rimeReady = rime->select_schema(session, "luna_pinyin_simp");
    if (!rimeReady)
      rimeReady = rime->select_schema(session, "luna_pinyin");
    rime->set_option(session, "ascii_mode", false);
    return rimeReady;
  }
  void updateRime() {
    RIME_STRUCT(RimeCommit, c);
    if (rime->get_commit(session, &c)) {
      commit(QString::fromUtf8(c.text));
      rime->free_commit(&c);
    }
    RIME_STRUCT(RimeContext, cx);
    preedit.clear();
    candidates = {};
    more = false;
    page = 0;
    if (rime->get_context(session, &cx)) {
      preedit = QString::fromUtf8(
          cx.composition.preedit ? cx.composition.preedit : "");
      for (int i = 0; i < cx.menu.num_candidates; ++i)
        candidates.append(QString::fromUtf8(cx.menu.candidates[i].text));
      page = cx.menu.page_no;
      more = !cx.menu.is_last_page;
      auto utf = preedit.toUtf8();
      int pos = std::clamp(cx.composition.cursor_pos, 0, int(utf.size()));
      zwp_input_method_v2_set_preedit_string(im, utf.constData(), pos, pos);
      zwp_input_method_v2_commit(im, state.serial);
      rime->free_context(&cx);
      flush();
    }
  }
  void loadDictionary(QString path) {
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly))
      return;
    QSet<QString> words;
    while (!f.atEnd()) {
      QString w =
          QString::fromUtf8(f.readLine(512)).trimmed().section('/', 0, 0);
      bool valid = w.size() > 1 && w.size() < 40;
      for (auto c : w)
        if (c < 'a' || c > 'z')
          valid = false;
      if (valid)
        words.insert(w);
    }
    dictionary = words.values();
    dictionary.sort();
  }
  void updateEnglish() {
    gestureResult = false;
    candidates = {};
    prefix.clear();
    if (secure() || !prediction || state.current.cursor != state.current.anchor)
      return;
    auto &ctx = state.current;
    if (ctx.cursor > ctx.surrounding.size())
      return;
    QByteArray before(ctx.surrounding.data(), ctx.cursor);
    int start = before.size();
    while (start > 0 &&
           ((before[start - 1] >= 'a' && before[start - 1] <= 'z') ||
            (before[start - 1] >= 'A' && before[start - 1] <= 'Z')))
      --start;
    prefix = QString::fromUtf8(before.mid(start));
    if (prefix.size() < 2)
      return;
    QString needle = prefix.toLower();
    auto it = std::lower_bound(dictionary.cbegin(), dictionary.cend(), needle);
    for (; it != dictionary.cend() && it->startsWith(needle) &&
           candidates.size() < 5;
         ++it) {
      if (*it == needle)
        continue;
      QString candidate = *it;
      if (prefix[0].isUpper())
        candidate[0] = candidate[0].toUpper();
      candidates.append(candidate);
    }
  }
  void command(QLocalSocket *s, const QJsonObject &o) {
    QString op = o["op"].toString();
    if (op == "status") {
      send(s, status());
      return;
    }
    if (op == "prediction") {
      prediction = o["enabled"].toBool();
      if (language == "en_US")
        updateEnglish();
      publish();
      return;
    }
    if (op == "manual") {
      bool next = o["enabled"].toBool();
      if (next != manual) {
        manual = next;
        bool hadPreedit = !preedit.isEmpty();
        reset();
        if (hadPreedit && state.current.active) {
          zwp_input_method_v2_set_preedit_string(im, "", 0, 0);
          zwp_input_method_v2_commit(im, state.serial);
          flush();
        }
      }
      publish();
      return;
    }
    if (op == "reset") {
      reset();
      if (state.current.active) {
        zwp_input_method_v2_set_preedit_string(im, "", 0, 0);
        zwp_input_method_v2_commit(im, state.serial);
        flush();
      }
      publish();
      return;
    }
    if (op == "language") {
      QString lang = o["language"].toString();
      if (lang != "en_US" && lang != "zh_CN") {
        error(s, "unsupported-language");
        return;
      }
      reset();
      if (lang == "zh_CN" && !initRime()) {
        error(s, "rime-unavailable");
        return;
      }
      language = lang;
      if (state.current.active) {
        zwp_input_method_v2_set_preedit_string(im, "", 0, 0);
        zwp_input_method_v2_commit(im, state.serial);
        flush();
      }
      publish();
      return;
    }
    if (!available || (!state.current.active && !manual)) {
      error(s, "no-active-text-input");
      return;
    }
    if (op == "gesture") {
      if (secure() || (gestureDecoder.isEmpty() && dictionary.isEmpty()) ||
          decoder || language != "en_US") {
        error(s, "gesture-unavailable");
        return;
      }
      auto keys = o["keys"].toArray();
      auto points = o["points"].toArray();
      if (keys.isEmpty() || keys.size() > 256 || points.size() > 2048) {
        error(s, "invalid-gesture");
        return;
      }
      if (gestureDecoder.isEmpty()) {
        QString trace;
        for (auto value : keys) {
          auto key = value.toString().toLower();
          if (key.size() != 1 || key[0] < 'a' || key[0] > 'z')
            continue;
          if (trace.isEmpty() || trace.back() != key[0])
            trace += key;
        }
        candidates = {};
        prefix.clear();
        if (trace.size() >= 2) {
          QList<QPair<double, QString>> ranked;
          for (const auto &word : dictionary) {
            if (word.front() != trace.front() || word.back() != trace.back())
              continue;
            QString target;
            for (auto c : word)
              if (target.isEmpty() || target.back() != c)
                target += c;
            // Real dictionary decoding: edit distance tolerates intervening
            // keys.
            QVector<int> row(target.size() + 1);
            for (int j = 0; j < row.size(); ++j)
              row[j] = j * 2;
            for (int i = 1; i <= trace.size(); ++i) {
              int diagonal = row[0];
              row[0] = i;
              for (int j = 1; j <= target.size(); ++j) {
                int previous = row[j];
                row[j] = std::min(
                    {row[j] + 1, row[j - 1] + 2,
                     diagonal + (trace[i - 1] == target[j - 1] ? 0 : 2)});
                diagonal = previous;
              }
            }
            double score =
                double(row.back()) / std::max(trace.size(), target.size());
            if (score <= 0.55)
              ranked.append({score, word});
          }
          std::sort(ranked.begin(), ranked.end(),
                    [](const auto &a, const auto &b) {
                      return a.first == b.first ? a.second < b.second
                                                : a.first < b.first;
                    });
          for (const auto &entry : ranked) {
            if (candidates.size() == 5)
              break;
            candidates.append(entry.second);
          }
        }
        gestureResult = !candidates.isEmpty();
        publish();
        return;
      }
      auto *process = new QProcess(&server);
      decoder = process;
      auto serial = state.serial;
      auto generation = contextGeneration;
      process->setProcessChannelMode(QProcess::SeparateChannels);
      QObject::connect(process, &QProcess::readyReadStandardError,
                       [process] { process->readAllStandardError(); });
      QObject::connect(process, &QProcess::readyReadStandardOutput, [process] {
        if (process->bytesAvailable() > 65536)
          process->kill();
      });
      QObject::connect(
          process,
          QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
          [this, process, serial, generation](int code,
                                              QProcess::ExitStatus exit) {
            auto bytes = process->readAllStandardOutput();
            if (code == 0 && exit == QProcess::NormalExit &&
                bytes.size() <= 65536 && !secure() && serial == state.serial &&
                generation == contextGeneration) {
              auto output = QJsonDocument::fromJson(bytes)
                                .object()["candidates"]
                                .toArray();
              candidates = {};
              prefix.clear();
              for (auto v : output) {
                auto word = v.toString();
                if (!word.isEmpty() && word.size() < 128 &&
                    candidates.size() < 10)
                  candidates.append(word);
              }
              gestureResult = !candidates.isEmpty();
              publish();
            }
            decoder = nullptr;
            process->deleteLater();
          });
      QObject::connect(process, &QProcess::errorOccurred,
                       [this, process](QProcess::ProcessError e) {
                         if (e == QProcess::FailedToStart) {
                           decoder = nullptr;
                           process->deleteLater();
                         }
                       });
      process->start(gestureDecoder, {});
      process->write(QJsonDocument(QJsonObject{{"keys", keys},
                                               {"points", points},
                                               {"language", language}})
                         .toJson(QJsonDocument::Compact) +
                     '\n');
      process->closeWriteChannel();
      QTimer::singleShot(2000, process, [process] {
        if (process->state() != QProcess::NotRunning)
          process->kill();
      });
      return;
    }
    bool chinese = language == "zh_CN" && !secure() && rimeReady;
    if (op == "text") {
      QString text = o["text"].toString();
      if (text.isEmpty() || text.toUtf8().size() > 4096) {
        error(s, "invalid-text-length");
        return;
      }
      if (chinese) {
        for (char32_t cp : text.toUcs4()) {
          if (cp < 128) {
            if (!rime->process_key(session, cp, 0))
              commit(QString(QChar(cp)));
            updateRime();
          } else {
            if (!preedit.isEmpty()) {
              rime->commit_composition(session);
              updateRime();
            }
            commit(QString::fromUcs4(&cp, 1));
          }
        }
      } else {
        if (!commit(text))
          error(s, "unicode-keymap-failed");
        candidates = {};
        prefix.clear();
      }
    } else if (op == "key") {
      QString key = o["key"].toString();
      auto sym = xkb_keysym_from_name(key.toUtf8().constData(),
                                      XKB_KEYSYM_CASE_INSENSITIVE);
      auto mods = o["modifiers"].toArray();
      if (sym == XKB_KEY_NoSymbol) {
        error(s, "unknown-key");
        return;
      }
      if (chinese && mods.isEmpty() && rime->process_key(session, sym, 0))
        updateRime();
      else {
        if (chinese && !preedit.isEmpty()) {
          rime->commit_composition(session);
          updateRime();
        }
        if (!rawSymbol(sym, mods))
          error(s, "unmapped-key");
      }
    } else if (op == "candidate") {
      int i = o["index"].toInt(-1);
      if (secure() || i < 0 || i >= candidates.size()) {
        error(s, "invalid-candidate");
        return;
      }
      if (gestureResult) {
        commit(candidates[i].toString());
        reset();
      } else if (chinese) {
        rime->select_candidate_on_current_page(session, i);
        updateRime();
      } else if (!prefix.isEmpty()) {
        QString chosen = candidates[i].toString();
        zwp_input_method_v2_delete_surrounding_text(im, prefix.toUtf8().size(),
                                                    0);
        commit(chosen);
        candidates = {};
        prefix.clear();
      }
    } else if (op == "page") {
      if (!chinese)
        return;
      int direction = o["direction"].toInt();
      if (direction != 1 && direction != -1)
        return;
      rime->process_key(session,
                        direction > 0 ? XKB_KEY_Page_Down : XKB_KEY_Page_Up, 0);
      updateRime();
    } else {
      error(s, "unknown-command");
      return;
    }
    publish();
  }
  bool listen() {
    QFileInfo fi(socketPath);
    QDir().mkpath(fi.absolutePath());
    struct stat st{};
    auto dir = fi.absolutePath().toUtf8();
    if (lstat(dir.constData(), &st) || !S_ISDIR(st.st_mode) ||
        st.st_uid != getuid())
      return false;
    chmod(dir.constData(), 0700);
    lockFd = open((socketPath + ".lock").toUtf8().constData(),
                  O_CREAT | O_RDWR | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (lockFd < 0 || flock(lockFd, LOCK_EX | LOCK_NB))
      return false;
    QLocalServer::removeServer(socketPath);
    server.setSocketOptions(QLocalServer::UserAccessOption);
    if (!server.listen(socketPath))
      return false;
    chmod(socketPath.toUtf8().constData(), 0600);
    QObject::connect(&server, &QLocalServer::newConnection, [this] {
      while (server.hasPendingConnections()) {
        auto *s = server.nextPendingConnection();
        struct ucred cred{};
        socklen_t len = sizeof(cred);
        if (getsockopt(s->socketDescriptor(), SOL_SOCKET, SO_PEERCRED, &cred,
                       &len) ||
            cred.uid != getuid() || clients.size() >= 8) {
          s->abort();
          s->deleteLater();
          continue;
        }
        clients.insert(s);
        send(s, status());
        QObject::connect(s, &QLocalSocket::disconnected, [this, s] {
          clients.remove(s);
          buffers.remove(s);
          s->deleteLater();
        });
        QObject::connect(s, &QLocalSocket::readyRead, [this, s] {
          auto &buf = buffers[s];
          buf += s->readAll();
          if (buf.size() > 16384) {
            s->abort();
            return;
          }
          while (buf.contains('\n')) {
            int n = buf.indexOf('\n');
            auto line = buf.left(n);
            buf.remove(0, n + 1);
            QJsonParseError err;
            auto doc = QJsonDocument::fromJson(line, &err);
            if (err.error != QJsonParseError::NoError || !doc.isObject()) {
              error(s, "invalid-json");
              continue;
            }
            command(s, doc.object());
          }
        });
      }
    });
    return true;
  }
};
int main(int argc, char **argv) {
  umask(0077);
  QCoreApplication app(argc, argv);
  QCoreApplication::setApplicationName("hp-os-input-backend");
  QCommandLineParser p;
  p.addHelpOption();
  p.addOptions(
      {QCommandLineOption("socket", "Private IPC socket", "path"),
       QCommandLineOption("rime-data", "Rime shared data directory", "path",
                          qEnvironmentVariable("HP_OS_RIME_DATA")),
       QCommandLineOption("dictionary", "Local English Hunspell word list",
                          "path", qEnvironmentVariable("HP_OS_DICTIONARY")),
       QCommandLineOption("gesture-decoder",
                          "Optional local decoder executable", "path"),
       QCommandLineOption(
           "probe", "Report protocol availability without claiming the seat")});
  p.process(app);
  Backend b;
  b.probe = p.isSet("probe");
  b.socketPath = p.value("socket");
  b.rimeData = p.value("rime-data");
  if (p.isSet("gesture-decoder")) {
    QFileInfo decoder(p.value("gesture-decoder"));
    if (!decoder.isAbsolute() || !decoder.isExecutable()) {
      fprintf(stderr, "hp-os: invalid gesture decoder\n");
      return 1;
    }
    b.gestureDecoder = decoder.absoluteFilePath();
  }
  b.loadDictionary(p.value("dictionary"));
  if (b.socketPath.isEmpty())
    b.socketPath =
        qEnvironmentVariable("XDG_RUNTIME_DIR") + "/hp-os-touch/input.sock";
  if (!b.connectWayland()) {
    fprintf(stderr, "hp-os: required Wayland protocols or seat unavailable\n");
    return b.unavailable ? 3 : 2;
  }
  if (b.probe) {
    QJsonObject o{{"inputMethodV2", b.manager != nullptr},
                  {"virtualKeyboardV1", b.vkManager != nullptr},
                  {"seat", b.seat != nullptr}};
    puts(QJsonDocument(o).toJson(QJsonDocument::Compact).constData());
    return 0;
  }
  if (!b.listen()) {
    fprintf(stderr, "hp-os: private IPC socket unavailable\n");
    return 1;
  }
  return app.exec();
}
