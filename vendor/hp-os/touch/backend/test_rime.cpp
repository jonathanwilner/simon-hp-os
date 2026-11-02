#include <cassert>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <rime_api.h>
#include <string>
int main() {
  const char *data = getenv("HP_OS_RIME_DATA");
  assert(data);
  auto path = std::filesystem::temp_directory_path() / "hp-os-rime-test";
  std::filesystem::create_directories(path);
  std::filesystem::permissions(path, std::filesystem::perms::owner_all);
  std::ofstream(path / "default.custom.yaml")
      << "patch:\n  schema_list:\n    - schema: luna_pinyin_simp\n";
  auto user = path.string();
  auto *r = rime_get_api();
  RIME_STRUCT(RimeTraits, t);
  t.shared_data_dir = data;
  t.user_data_dir = user.c_str();
  t.app_name = "rime.hp-os-test";
  t.min_log_level = 3;
  t.log_dir = "";
  r->setup(&t);
  r->initialize(&t);
  r->start_maintenance(false);
  r->join_maintenance_thread();
  assert(r->deploy_schema(
      (std::string(data) + "/luna_pinyin_simp.schema.yaml").c_str()));
  auto s = r->create_session();
  assert(s);
  assert(r->select_schema(s, "luna_pinyin_simp"));
  r->set_option(s, "ascii_mode", false);
  for (char c : std::string("nihao"))
    assert(r->process_key(s, c, 0));
  RIME_STRUCT(RimeContext, ctx);
  assert(r->get_context(s, &ctx));
  assert(ctx.menu.num_candidates > 0);
  assert(ctx.composition.length > 0);
  bool found = false;
  int index = -1;
  for (int i = 0; i < ctx.menu.num_candidates; ++i)
    if (std::string(ctx.menu.candidates[i].text) == "你好") {
      found = true;
      index = i;
    }
  assert(found);
  r->free_context(&ctx);
  assert(r->select_candidate_on_current_page(s, index));
  RIME_STRUCT(RimeCommit, commit);
  assert(r->get_commit(s, &commit));
  assert(std::string(commit.text) == "你好");
  r->free_commit(&commit);
  r->clear_composition(s);
  r->destroy_session(s);
  r->finalize();
  std::filesystem::remove_all(path);
}
