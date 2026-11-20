const cloud = require("wx-server-sdk");
const cloudbase = require("@cloudbase/node-sdk");

cloud.init({env: cloud.DYNAMIC_CURRENT_ENV});
const app = cloudbase.init({env: cloudbase.SYMBOL_CURRENT_ENV});

exports.main = async (event = {}) => {
  const {action, payload} = event;
  let rpc;
  let params = {};
  if (action === "health") {
    rpc = "wordnet_vocab_health";
  } else {
    const {OPENID} = cloud.getWXContext();
    if (!OPENID) return {ok: false, code: "UNAUTHENTICATED"};
    if (action === "wordbook.list") {
      rpc = "wordnet_vocab_books";
    } else if (action === "word.lookup") {
      if (typeof payload?.lemma !== "string" || payload.lemma.length > 140) {
        return {ok: false, code: "INVALID_LEMMA"};
      }
      const lemma = payload.lemma.normalize("NFKC").trim().toLowerCase().replace(/\s+/g, " ");
      if (!lemma) return {ok: false, code: "INVALID_LEMMA"};
      rpc = "wordnet_vocab_word";
      params = {p_lemma: lemma};
    } else {
      return {ok: false, code: "UNKNOWN_ACTION"};
    }
  }
  try {
    const {data, error} = await app.rdb().rpc(rpc, params);
    if (error) return {ok: false, code: "DATABASE_ERROR"};
    if (action === "word.lookup" && data == null) return {ok: false, code: "NOT_FOUND"};
    return {ok: true, data};
  } catch {
    return {ok: false, code: "DATABASE_ERROR"};
  }
};
