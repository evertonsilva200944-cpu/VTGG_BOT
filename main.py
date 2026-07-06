import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters, ContextTypes
)

# Lê as variáveis do Railway automaticamente
TOKEN = os.environ["TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])

DADOS_FILE = "dados.json"
AGUARDANDO_NOME = 1
AGUARDANDO_ARQUIVO = 2


# ========== UTILITÁRIOS ==========

def carregar_dados():
    if not os.path.exists(DADOS_FILE):
        return {"pix": "", "preco": 5.00, "produtos": {}, "proximo_id": 1}
    with open(DADOS_FILE, "r") as f:
        return json.load(f)


def salvar_dados(dados):
    with open(DADOS_FILE, "w") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def is_admin(user_id):
    return user_id == ADMIN_ID


# ========== CLIENTE ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dados = carregar_dados()
    produtos = dados["produtos"]

    if not produtos:
        await update.message.reply_text("⚠️ Nenhum produto disponível no momento.")
        return

    botoes = []
    for id, p in produtos.items():
        botoes.append([InlineKeyboardButton(
            f"🛒 {p['nome']} — R${dados['preco']:.2f}",
            callback_data=f"comprar_{id}"
        )])

    await update.message.reply_text(
        "👋 Bem-vindo! Escolha seu produto:",
        reply_markup=InlineKeyboardMarkup(botoes)
    )


async def comprar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    dados = carregar_dados()
    produto_id = query.data.split("_")[1]

    if produto_id not in dados["produtos"]:
        await query.message.reply_text("⚠️ Produto não encontrado.")
        return

    produto = dados["produtos"][produto_id]

    botao_pago = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Já paguei", callback_data=f"pago_{produto_id}")
    ]])

    mensagem = (
        f"✅ Você escolheu: *{produto['nome']}*\n\n"
        f"💰 Valor: R${dados['preco']:.2f}\n\n"
        f"🏦 Chave PIX: `{dados['pix']}`\n\n"
        f"Após realizar o pagamento, clique no botão abaixo."
    )
    await query.message.reply_text(
        mensagem,
        parse_mode="Markdown",
        reply_markup=botao_pago
    )


async def ja_paguei(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    produto_id = query.data.split("_")[1]
    dados = carregar_dados()
    produto = dados["produtos"][produto_id]

    await context.bot.send_message(
        ADMIN_ID,
        f"🔔 Novo pedido!\n"
        f"👤 @{user.username} (ID: {user.id})\n"
        f"📦 Produto: {produto['nome']}\n\n"
        f"Use /aprovar_{user.id}_{produto_id} para entregar."
    )
    await query.message.reply_text("⏳ Aguarde, seu acesso está sendo liberado!")


async def aprovar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return

    partes = update.message.text.split("_")
    user_id = int(partes[1])
    produto_id = partes[2]
    dados = carregar_dados()
    produto = dados["produtos"][produto_id]

    await context.bot.send_document(
        user_id,
        document=produto["file_id"],
        caption=f"✅ Pagamento confirmado! Aqui está seu *{produto['nome']}*.",
        parse_mode="Markdown"
    )
    await update.message.reply_text("✅ Produto entregue!")


# ========== ADMIN ==========

async def painel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return

    dados = carregar_dados()
    texto = (
        "⚙️ *Painel Admin*\n\n"
        f"💰 Preço: R${dados['preco']:.2f}\n"
        f"🏦 PIX: `{dados['pix'] or 'não definido'}`\n"
        f"📦 Produtos: {len(dados['produtos'])}\n\n"
        "*Comandos disponíveis:*\n"
        "/setpix [chave] — definir PIX\n"
        "/setpreco [valor] — definir preço\n"
        "/addproduto — adicionar produto\n"
        "/listarprodutos — listar produtos\n"
        "/removerproduto [id] — remover produto"
    )
    await update.message.reply_text(texto, parse_mode="Markdown")


async def setpix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return

    if not context.args:
        await update.message.reply_text("❌ Use: /setpix sua@chave.com")
        return

    dados = carregar_dados()
    dados["pix"] = " ".join(context.args)
    salvar_dados(dados)
    await update.message.reply_text(
        f"✅ Chave PIX definida: `{dados['pix']}`",
        parse_mode="Markdown"
    )


async def setpreco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return

    if not context.args:
        await update.message.reply_text("❌ Use: /setpreco 5.00")
        return

    try:
        preco = float(context.args[0].replace(",", "."))
        dados = carregar_dados()
        dados["preco"] = preco
        salvar_dados(dados)
        await update.message.reply_text(f"✅ Preço definido: R${preco:.2f}")
    except Exception:
        await update.message.reply_text("❌ Valor inválido. Use: /setpreco 5.00")


async def addproduto_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return ConversationHandler.END

    await update.message.reply_text("📝 Qual o *nome* do produto?", parse_mode="Markdown")
    return AGUARDANDO_NOME


async def addproduto_nome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["novo_produto_nome"] = update.message.text
    await update.message.reply_text(
        "📎 Agora envie o *arquivo* do produto.",
        parse_mode="Markdown"
    )
    return AGUARDANDO_ARQUIVO


async def addproduto_arquivo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document:
        await update.message.reply_text("❌ Envie um arquivo válido.")
        return AGUARDANDO_ARQUIVO

    file_id = update.message.document.file_id
    nome = context.user_data["novo_produto_nome"]

    dados = carregar_dados()
    id_novo = str(dados["proximo_id"])
    dados["produtos"][id_novo] = {"nome": nome, "file_id": file_id}
    dados["proximo_id"] += 1
    salvar_dados(dados)

    await update.message.reply_text(
        f"✅ Produto *{nome}* adicionado com ID `{id_novo}`!",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operação cancelada.")
    return ConversationHandler.END


async def listarprodutos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return

    dados = carregar_dados()

    if not dados["produtos"]:
        await update.message.reply_text("⚠️ Nenhum produto cadastrado.")
        return

    texto = "📦 *Produtos cadastrados:*\n\n"
    for id, p in dados["produtos"].items():
        texto += f"ID `{id}` — {p['nome']}\n"

    await update.message.reply_text(texto, parse_mode="Markdown")


async def removerproduto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return

    if not context.args:
        await update.message.reply_text("❌ Use: /removerproduto [id]")
        return

    produto_id = context.args[0]
    dados = carregar_dados()

    if produto_id not in dados["produtos"]:
        await update.message.reply_text("❌ Produto não encontrado.")
        return

    nome = dados["produtos"][produto_id]["nome"]
    del dados["produtos"][produto_id]
    salvar_dados(dados)
    await update.message.reply_text(
        f"✅ Produto *{nome}* removido!",
        parse_mode="Markdown"
    )


# ========== MAIN ==========

app = ApplicationBuilder().token(TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("addproduto", addproduto_start)],
    states={
        AGUARDANDO_NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, addproduto_nome)],
        AGUARDANDO_ARQUIVO: [MessageHandler(filters.Document.ALL, addproduto_arquivo)],
    },
    fallbacks=[CommandHandler("cancelar", cancelar)],
)

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("painel", painel))
app.add_handler(CommandHandler("setpix", setpix))
app.add_handler(CommandHandler("setpreco", setpreco))
app.add_handler(CommandHandler("listarprodutos", listarprodutos))
app.add_handler(CommandHandler("removerproduto", removerproduto))
app.add_handler(conv_handler)
app.add_handler(CallbackQueryHandler(comprar, pattern="^comprar_"))
app.add_handler(CallbackQueryHandler(ja_paguei, pattern="^pago_"))
app.add_handler(MessageHandler(filters.Regex(r"^/aprovar_"), aprovar))

app.run_polling()
