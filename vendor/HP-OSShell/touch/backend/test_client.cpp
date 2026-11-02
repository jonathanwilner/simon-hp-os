// Isolated acceptance fixture. Never attach this helper to a live user session.
#include <QApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QKeyEvent>
#include <QLineEdit>
class RawWidget : public QWidget {
public:
  QString text;
  RawWidget() { setFocusPolicy(Qt::StrongFocus); }
  void keyPressEvent(QKeyEvent *e) override { text += e->text(); }
};
#include <QLocalServer>
#include <QLocalSocket>
#include <QTimer>
#include <QVBoxLayout>
int main(int argc, char **argv) {
  QApplication app(argc, argv);
  if (argc != 2)
    return 2;
  QWidget window;
  window.setWindowTitle("HP-OS input acceptance fixture");
  QVBoxLayout layout(&window);
  QLineEdit normal, password;
  RawWidget raw;
  layout.addWidget(&raw);
  password.setEchoMode(QLineEdit::Password);
  layout.addWidget(&normal);
  layout.addWidget(&password);
  window.resize(600, 180);
  window.show();
  normal.setFocus();
  QLocalServer server;
  server.setSocketOptions(QLocalServer::UserAccessOption);
  if (!server.listen(argv[1]))
    return 3;
  QObject::connect(&server, &QLocalServer::newConnection, [&] {
    while (server.hasPendingConnections()) {
      auto *s = server.nextPendingConnection();
      QObject::connect(s, &QLocalSocket::disconnected, s,
                       &QObject::deleteLater);
      QObject::connect(s, &QLocalSocket::readyRead, [&, s] {
        while (s->canReadLine()) {
          auto o = QJsonDocument::fromJson(s->readLine()).object();
          auto op = o["op"].toString();
          if (op == "raw")
            raw.setFocus();
          if (op == "normal")
            normal.setFocus();
          if (op == "password")
            password.setFocus();
          if (op == "clear") {
            normal.clear();
            password.clear();
          }
          QTimer::singleShot(100, s, [&, s] {
            QJsonObject state{
                {"normal", normal.text()},
                {"raw", raw.text},
                {"password", password.text()},
                {"focus", password.hasFocus() ? "password" : "normal"}};
            s->write(QJsonDocument(state).toJson(QJsonDocument::Compact) +
                     '\n');
          });
        }
      });
    }
  });
  return app.exec();
}
