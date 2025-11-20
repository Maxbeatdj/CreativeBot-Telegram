import yt_dlp
import instaloader
import os 
import re 
import logging 
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters 

# Configuração básica de log para que os erros apareçam no terminal
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 1. TOKEN DE ACESSO DO SEU BOT
api_token = '8343410661:AAHpNlh1MWmfcNF0d0hR1Jd2AMuPFu0B1Aw'

# 2. CONFIGURAÇÃO INSTAGRAM
# Use o número de telefone completo que você usou para o login do Instaloader
INSTAGRAM_USERNAME = '+5544997022416' 
L = instaloader.Instaloader()

# 3. CONFIGURAÇÃO YT-DLP (YouTube, X, Facebook, etc.)
# OTIMIZAÇÃO: Força MP4 com qualidade máxima de 480p para garantir o envio no Telegram (limite de 50MB)
YDL_OPTS_TELEGRAM = {
    'format': 'bestvideo[ext=mp4][height<=480]+bestaudio[ext=m4a]/best[ext=mp4][height<=480]/best', 
    'outtmpl': 'downloads/%(title)s.%(ext)s', 
    'noplaylist': True, 
    'quiet': True, 
    'no_warnings': True,
}


# --- Funções do Bot ---

async def start(update, context):
    """Envia uma mensagem de boas-vindas."""
    user = update.effective_user
    await update.message.reply_markdown(
        f'Oi, {user.mention_markdown()}! Eu sou o **CreativeBot**.'
        f'\nMe manda um link de vídeo (YouTube, X, Facebook, etc.) ou imagem/vídeo (Instagram) para eu tentar baixar para você!'
    )

async def help_command(update, context):
    """Envia um guia de uso."""
    await update.message.reply_text(
        'Como usar o CreativeBot:\n'
        '1. Envie um link de vídeo do **YouTube, X, Facebook, etc.** (Usamos yt-dlp).\n'
        '2. Envie um link de postagem do **Instagram** (Requer login e funciona para fotos e vídeos).'
    )

async def error_handler(update, context):
    """Loga e notifica o usuário sobre erros não tratados."""
    logger.error("Exceção não tratada:", exc_info=context.error)
    if update.effective_chat:
        await update.effective_chat.send_message(
            '🚨 **Desculpe, houve um erro inesperado!** Tente novamente ou use outro link.',
            parse_mode='Markdown'
        )

async def download_instagram(update, message, url):
    """Lógica para baixar mídia do Instagram usando Instaloader."""
    
    # 1. Carrega a sessão (usando o nome de arquivo correto)
    try:
        L.load_session_from_file(INSTAGRAM_USERNAME, f'session-{INSTAGRAM_USERNAME}') 
    except Exception as e:
        await message.edit_text(f'❌ Erro ao carregar sessão do Instagram. Certifique-se de ter feito login e movido o arquivo de sessão `session-{INSTAGRAM_USERNAME}` para a pasta do bot. Detalhes: {e}')
        return
        
    # 2. Tenta baixar o post
    try:
        # Extrai o shortcode (código do post) do URL
        post_url_part = url.split("/")[-2]
        post = instaloader.Post.from_shortcode(L.context, post_url_part)
        
        # Define a pasta de download
        L.dirname_pattern = "downloads"
        
        # Baixa o post (o nome do arquivo será baseado na data)
        L.download_post(post, target=post.date_utc.strftime('%Y-%m-%d'))
        
        # 3. Encontra o arquivo e envia para o Telegram
        sent = False
        for filename in os.listdir('downloads'):
            # Busca pelo nome do arquivo que contenha a data E a extensão de mídia
            if post.date_utc.strftime('%Y-%m-%d') in filename and filename.endswith(('.mp4', '.jpg', '.jpeg')):
                full_path = os.path.join('downloads', filename)
                
                await message.edit_text('Download concluído! Enviando arquivo...')
                
                with open(full_path, 'rb') as media_file:
                    caption_text = f"✅ Baixado por CreativeBot\nPost: {url}"
                    if filename.endswith(('.mp4')):
                        await update.message.reply_video(video=media_file, caption=caption_text)
                    else:
                        await update.message.reply_photo(photo=media_file, caption=caption_text)
                
                # Deleta o arquivo após o envio
                os.remove(full_path)
                sent = True
        
        # 4. Limpeza e Finalização
        # Deleta arquivos auxiliares do Instaloader (.json, .txt)
        for f in os.listdir('downloads'):
             if f.startswith(post.date_utc.strftime('%Y-%m-%d')):
                  os.remove(os.path.join('downloads', f))
        
        if not sent:
            await message.edit_text('❌ Arquivo baixado, mas não foi possível identificar o arquivo de mídia para envio.')
        
    except instaloader.exceptions.InstaloaderException as e:
        await message.edit_text(f'❌ Erro do Instaloader (Post Privado ou link inválido). Detalhes: {e}')
    except Exception as e:
        await message.edit_text(f'🚨 Ocorreu um erro inesperado no Instagram. Detalhes: {e}')
        

async def download_video(update, context):
    """Função principal que roteia o link para a ferramenta correta."""
    url = update.message.text
    
    message = await update.message.reply_text('Recebi o link. Analisando a plataforma...')

    # 1. Roteamento: INSTAGRAM
    if re.search(r'instagram\.com', url, re.IGNORECASE):
        await message.edit_text('Link do Instagram detectado. Tentando baixar via Instaloader...')
        await download_instagram(update, message, url)
        return

    # 2. Roteamento: YT-DLP (YouTube, X, Facebook, etc.)
    await message.edit_text('Link de vídeo detectado. Tentando processar e baixar com yt-dlp (Otimizado 480p)...')

    try:
        with yt_dlp.YoutubeDL(YDL_OPTS_TELEGRAM) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info_dict)

        await message.edit_text('Download concluído! Enviando arquivo...')

        with open(filename, 'rb') as media_file:
            if info_dict.get('ext') in ['mp4', 'webm', 'mkv', 'mov']:
                await update.message.reply_video(
                    video=media_file,
                    caption=f"✅ Baixado por CreativeBot\nTítulo: {info_dict.get('title', 'N/A')}"
                )
            else:
                 await update.message.reply_document(
                    document=media_file,
                    caption=f"✅ Baixado por CreativeBot\nTítulo: {info_dict.get('title', 'N/A')}"
                )

        os.remove(filename)
        
    except yt_dlp.DownloadError as e: 
        await message.edit_text(
            f'❌ Erro ao baixar ou formato não suportado com yt-dlp. Detalhes: {str(e)[:100]}...'
        )
    except Exception as e:
        await message.edit_text(
            f'🚨 Ocorreu um erro inesperado no processamento. Detalhes: {str(e)[:100]}...'
        )


def main():
    """Inicia o bot usando ApplicationBuilder."""
    
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
        
    application = ApplicationBuilder().token(api_token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_error_handler(error_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))
    
    print(f"CreativeBot iniciado e escutando. Usuário Insta: {INSTAGRAM_USERNAME}")
    application.run_polling()


if __name__ == '__main__':
    main()