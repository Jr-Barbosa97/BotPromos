import asyncio
import logging
import sys
import aiohttp

logging.basicConfig(
    stream=sys.stdout,
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.request import HTTPXRequest

TOKEN_TELEGRAM = "9234115472:AAFHQtxk3jkdKjdaqdH2vXmopD4qH5CTNh0"
CANAL_ID = "@MeusjogosSteam"
URL_STEAM_FEAT = "https://store.steampowered.com/api/featuredcategories/?cc=br&l=portuguese"

enviados_historico = set()

async def obter_catalogo_ordenado(session):
    try:
        async with session.get(URL_STEAM_FEAT, timeout=30) as resp:
            if resp.status == 200:
                dados = await resp.json()
                jogos_dict = {}
                for chave, conteudo in dados.items():
                    if isinstance(conteudo, dict) and "items" in conteudo:
                        for item in conteudo["items"]:
                            appid = item.get("id")
                            if appid and appid not in jogos_dict:
                                item["final_price"] = item.get("final_price") or 0
                                item["original_price"] = item.get("original_price") or 0
                                item["discount_percent"] = item.get("discount_percent") or 0
                                jogos_dict[appid] = item
                
                lista_jogos = list(jogos_dict.values())
                lista_jogos.sort(key=lambda x: x.get("final_price", 0))
                return lista_jogos
    except Exception as e:
        logging.error(f"⚠️ Erro ao consultar a API da Steam: {e}")
    return []

def gerar_card_jogo(jogo):
    titulo = jogo.get("name", "Jogo Steam")
    preco_orig = (jogo.get("original_price") or 0) / 100.0
    preco_final = (jogo.get("final_price") or 0) / 100.0
    desconto = jogo.get("discount_percent") or 0
    
    if desconto > 0:
        tag = "🛡️ <b>EAGLEBOY — ALERTA DE PROMOÇÃO</b> 🦅"
        preco_txt = (
            f"💰 <b>Condições da Arena:</b>\n"
            f"• De: <s>R$ {preco_orig:.2f}</s>\n"
            f"• Por: <b>R$ {preco_final:.2f}</b> ({desconto}% OFF)\n"
        )
    elif preco_final == 0.0:
        tag = "📌 <b>EAGLEBOY — CATÁLOGO STEAM</b> 📚"
        preco_txt = "💰 <b>Valor:</b> 🟢 <b>GRATUITO PARA JOGAR (F2P)</b>\n"
    else:
        tag = "📌 <b>EAGLEBOY — CATÁLOGO STEAM</b> 📚"
        preco_txt = f"💰 <b>Preço de Tabela:</b> <b>R$ {preco_final:.2f}</b>\n"

    return (
        f"{tag}\n\n"
        f"🎮 <b>{titulo}</b>\n\n"
        f"{preco_txt}\n"
        f"⚡ <i>Acesse a loja para conferir os detalhes!</i>"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🦅 <b>EagleBoy Monitor Ativo!</b>", parse_mode="HTML")

async def loop_monitoramento(app):
    bot = app.bot
    logging.info("🚀 [MONITOR STEAM] Varredura contínua iniciada...")
    await asyncio.sleep(2)

    global enviados_historico

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                logging.info("🔍 Coletando dados atualizados da Steam...")
                jogos = await obter_catalogo_ordenado(session)
                
                if jogos:
                    novos_enviados = 0
                    for jogo in jogos:
                        appid = jogo.get("id")
                        if appid in enviados_historico:
                            continue
                            
                        thumb = jogo.get("header_image", "")
                        link = f"https://store.steampowered.com/app/{appid}/"
                        
                        is_promo_ou_gratuito = (jogo.get("discount_percent") or 0) > 0 or (jogo.get("final_price") or 0) == 0
                        btn_txt = "🛒 Resgatar na Steam" if is_promo_ou_gratuito else "📚 Ver Página na Steam"
                        
                        keyboard = InlineKeyboardMarkup([[
                            InlineKeyboardButton(btn_txt, url=link)
                        ]])
                        
                        try:
                            await bot.send_photo(
                                chat_id=CANAL_ID,
                                photo=thumb,
                                caption=gerar_card_jogo(jogo),
                                parse_mode="HTML",
                                reply_markup=keyboard
                            )
                            enviados_historico.add(appid)
                            novos_enviados += 1
                            preco_fmt = f"R$ {(jogo.get('final_price') or 0) / 100.0:.2f}"
                            logging.info(f"✅ [ENVIADO] {jogo.get('name')} | Preço: {preco_fmt}")
                        except Exception as telegram_error:
                            logging.error(f"Erro ao enviar foto para o Telegram: {telegram_error}")
                        
                        await asyncio.sleep(15)

                    if novos_enviados == 0:
                        logging.info("🔄 Ciclo completo finalizado. Reiniciando histórico!")
                        enviados_historico.clear()
                else:
                    logging.info("⚠️ Nenhum jogo retornado nesta tentativa. Tentando novamente em instantes...")

            except Exception as e:
                logging.error(f"⚠️ Erro no loop principal: {e}")
            
            await asyncio.sleep(30)

async def main():
    # Configura timeouts estendidos de conexão com o Telegram (30 segundos)
    request_config = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0)
    
    app = ApplicationBuilder().token(TOKEN_TELEGRAM).request(request_config).build()
    app.add_handler(CommandHandler("start", start))

    logging.info("Conectando ao Telegram (aguarde)...")
    
    # Bloco de segurança para tentar conectar sem derrubar o script se a rede oscilar
    while True:
        try:
            await app.initialize()
            await app.start()
            await app.updater.start_polling()
            break
        except Exception as e:
            logging.error(f"⚠️ Falha ao conectar ao Telegram ({e}). Tentando novamente em 10 segundos...")
            await asyncio.sleep(10)

    logging.info(f"🚀 Robô Monitor conectado e pronto para disparar no canal {CANAL_ID}!")
    asyncio.create_task(loop_monitoramento(app))

    stop_signal = asyncio.Event()
    await stop_signal.wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Robô encerrado com segurança.")