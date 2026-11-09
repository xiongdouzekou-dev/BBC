import os
import json
import requests
import asyncio
import random
from openai import OpenAI
import edge_tts
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip
import moviepy.video.fx.all as vfx

# APIキー読み込み
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY")

# OpenAIクライアント初期化
client = OpenAI(api_key=OPENAI_API_KEY)

# 自動実行時のテーマリスト
THEME_LIST = [
    "明太子の絶品アレンジレシピ",
    "スーパーの割引お肉を高級ステーキにする裏技",
    "業務スーパーの隠れた神コスパおやつ3選",
    "深夜に食べても罪悪感ゼロの夜食レシピ",
    "100円以下で作れる極上卵かけご飯",
    "実は冷凍した方が美味しい意外な食材"
]

def get_video_settings():
    manual_theme = os.environ.get("CUSTOM_THEME")
    manual_tone = os.environ.get("CUSTOM_TONE")
    
    theme = manual_theme if manual_theme else random.choice(THEME_LIST)
    tone = manual_tone if manual_tone else "テンション高めで視聴者を引き込む口調"
    
    return theme, tone

def generate_script(theme, tone):
    prompt = f"""
    TikTok用のショート動画台本を作成してください。
    
    【テーマ】: {theme}
    【口調・スタイル】: {tone}
    【長さ】: 30秒程度
    
    必ず以下のJSON形式のみを出力してください。
    {{
      "text": "読み上げる台本のテキスト。",
      "keyword": "背景動画を探すための英語の検索キーワード(例: cooking pasta, night city, etc)"
    }}
    """
    
    # Omniモデル（gpt-4o-mini）による生成
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that outputs strictly in JSON format."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    
    raw_text = response.choices[0].message.content
    return json.loads(raw_text)

async def generate_audio(text, output_file="audio.mp3"):
    communicate = edge_tts.Communicate(text, "ja-JP-NanamiNeural")
    await communicate.save(output_file)

def download_pixabay_video(keyword, output_file="bg_video.mp4"):
    url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q={requests.utils.quote(keyword)}&video_type=all"
    res = requests.get(url)
    data = res.json()
    
    if data.get("totalHits", 0) > 0:
        video_url = data["hits"][0]["videos"]["medium"]["url"]
    else:
        fallback_url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q=food&video_type=all"
        video_url = requests.get(fallback_url).json()["hits"][0]["videos"]["medium"]["url"]

    video_data = requests.get(video_url).content
    with open(output_file, "wb") as f:
        f.write(video_data)

def create_video(audio_file, video_file, script_text, output_file="final_video.mp4"):
    audio = AudioFileClip(audio_file)
    bg = VideoFileClip(video_file)
    
    target_w = bg.h * 9 / 16
    if bg.w > target_w:
        bg = bg.crop(x_center=bg.w / 2, width=target_w)
    
    if bg.duration < audio.duration:
        bg = bg.fx(vfx.loop, duration=audio.duration)
    else:
        bg = bg.subclip(0, audio.duration)
        
    bg = bg.set_audio(audio)
    
    txt_clip = TextClip(script_text, fontsize=45, color='white', font="Noto-Sans-CJK-JP",
                        stroke_color='black', stroke_width=2, method='caption', 
                        size=(bg.w * 0.85, None))
    txt_clip = txt_clip.set_position('center').set_duration(audio.duration)
    
    video = CompositeVideoClip([bg, txt_clip])
    
    video.write_videofile(
        output_file, 
        fps=30, 
        codec="libx264", 
        audio_codec="aac", 
        bitrate="3000k"
    )

async def main():
    theme, tone = get_video_settings()
    print(f"採用テーマ: {theme} / 口調: {tone}")
    
    print("1. OpenAI (gpt-4o-mini) で台本生成中...")
    script_data = generate_script(theme, tone)
    
    print("2. 音声生成中...")
    await generate_audio(script_data['text'])
    
    print("3. 動画素材ダウンロード中...")
    download_pixabay_video(script_data['keyword'])
    
    print("4. 動画合成中...")
    create_video("audio.mp3", "bg_video.mp4", script_data['text'])
    
    print("🎉 高画質動画の生成が完了しました！")

if __name__ == "__main__":
    asyncio.run(main())
