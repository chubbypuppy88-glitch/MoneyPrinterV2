#!/usr/bin/env python3
from __future__ import annotations
import argparse
import base64
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import requests
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OPENMIND_IMAGE_URL = "https://openmind.theeverythingai.com/v1/images/generations"

TOPICS = [
("Why Maine Coons chirp instead of meow","That tiny chirp is one of the funniest Maine Coon sounds. They often use trills and chirps to get attention or react to something interesting. Their huge body makes the tiny sound even more ridiculous. House of Big Beans approves this extremely serious communication style."),
("Why Maine Coons follow you everywhere","A Maine Coon can turn a quiet walk through the house into a full security detail. They are famously social and often prefer being near their people without demanding constant lap time. That means bathroom trips, laundry runs, and snack missions may all get supervised. Privacy is apparently not part of the House of Big Beans contract."),
("The Maine Coon tail is basically a feather duster","A Maine Coon tail can look almost as dramatic as the cat itself. The long fur helps protect against cold weather and wraps around the body like a built-in blanket. It also makes every walk through the room look ten times more important. Somewhere, a normal-sized tail is feeling inadequate."),
("Why Maine Coons look like tiny lions","The Maine Coon's heavy ruff, tufted ears, and broad face can make it look like a miniature lion. Add a giant fluffy tail and suddenly the living room has its own wildlife documentary. The intimidating look is often paired with a surprisingly goofy personality. House of Big Beans calls that excellent branding."),
("Why Maine Coons love high places","A tall perch gives a Maine Coon a perfect view of everything happening below. Climbing also gives these athletic cats a chance to use their size and coordination. From the top of a cat tree, every human activity becomes worthy of inspection. Congratulations, you now live under management."),
("Maine Coon paws are ridiculously big","Those oversized Maine Coon paws are not just for dramatic effect. Large feet helped the breed move across cold, snowy ground, and many have extra fur between their toes. Indoors, the same paws are excellent for opening cabinets and knocking things off tables. Nature created snowshoes; the cat created chaos."),
("Why Maine Coons act like dogs","People often call Maine Coons dog-like because many enjoy following humans, greeting visitors, and learning simple games. Some even play fetch when they feel like cooperating. The important phrase is when they feel like it. House of Big Beans recognizes no authority above the cat."),
("The slow blink cat compliment","When a relaxed cat slowly closes and opens its eyes around you, that is often a sign of comfort and trust. Returning a gentle slow blink can be a calm way to interact without touching. With a Maine Coon, the effect is extra dramatic because everything about the face is oversized. Consider yourself officially tolerated."),
("Why cats squeeze into tiny boxes","Cats often choose boxes because enclosed spaces can feel secure, warm, and easy to defend. The funny part is that cats rarely seem concerned about whether the box actually fits. A giant Maine Coon attempting the same strategy turns basic cat behavior into physical comedy. If the paws are inside, the box counts."),
("Maine Coon ear tufts explained","Those dramatic hairs on the tips and inside of a Maine Coon's ears are more than decoration. Extra fur can help protect the ears from debris and cold air. It also gives the breed its famous wild, lynx-like appearance. The cat did not request the deluxe package; nature installed it anyway."),
("Why cats knead blankets","Kneading starts when kittens press against their mother while nursing. Many adult cats keep the behavior because it is comforting and may also help mark a favorite resting place. On a fluffy Maine Coon, the giant paws make biscuit-making look industrial. House of Big Beans is now accepting bakery orders."),
("Maine Coons can take years to fully grow","Maine Coons are known for maturing more slowly than many smaller cat breeds. Their bodies can keep filling out for several years before reaching full adult size. That means the enormous cat in your hallway may still be upgrading. Please allow additional space for future expansion."),
("Why cats stare out windows for hours","A window gives an indoor cat a constantly changing stream of birds, insects, people, shadows, and movement. Watching all of that can provide valuable mental stimulation. For a Maine Coon, the windowsill becomes a private observation deck. Neighborhood surveillance is apparently a full-time position."),
("The Maine Coon winter coat","Maine Coons developed a thick, water-resistant coat suited to cold climates. Their fur is especially long around the belly, chest, and tail, creating a natural layer of insulation. Inside a warm house, that same winter equipment produces spectacular fluff. Seasonal shedding is the price humans pay for greatness."),
("Why cats head-butt people","When a cat gently bumps its head or cheek against you, it can be both affectionate and a way of leaving familiar scent. Cats have scent glands around the face that help mark safe people and places. A Maine Coon head-bump has a little more momentum than average. Affection may arrive with measurable force."),
("Maine Coons and water","Many Maine Coons show unusual curiosity around sinks, tubs, and running water. Their dense coats can handle moisture better than the coats of many cats, although every individual is different. Some will tap the water before drinking like tiny scientists. Peer review is still pending."),
("Why cats sleep so much","Cats can spend a large part of the day sleeping or lightly dozing because their bodies are built around short bursts of intense activity. Rest helps conserve energy for climbing, chasing, and midnight nonsense. A Maine Coon simply requires a larger sleeping surface. The cat will still choose the smallest one available."),
("Why Maine Coons are called gentle giants","Maine Coons are one of the largest domestic cat breeds, but many are known for calm and social temperaments. Their size can look intimidating until the giant cat starts chirping at a toy. That contrast helped create the nickname gentle giant. Large body, tiny noises, excellent comedy."),
("Why cats show you their belly","A cat exposing its belly can be a strong sign that it feels safe and relaxed. It is not always an invitation for a belly rub, because the stomach is still a vulnerable area. Reading the rest of the cat's body language matters. House of Big Beans recommends admiring the fluff before making risky decisions."),
("Maine Coon whiskers are serious equipment","A cat's whiskers are sensitive tools that help detect nearby objects and changes in air movement. Maine Coons often have especially long whiskers that match their broad faces. Those whiskers help judge tight spaces before the body follows. Whether the cat respects that information is a separate question."),
("Why cats suddenly sprint at night","Those random nighttime sprints are often called the zoomies. Cats naturally have bursts of energy, especially around dawn and dusk when their wild ancestors would be active. A large Maine Coon doing full-speed laps adds noticeable sound effects. Sleep is optional when the hallway racetrack opens."),
("Maine Coon toe fluff","The long fur growing between a Maine Coon's toes is sometimes called toe fluff or snowshoe fur. It helped protect paws from cold surfaces and snow. Indoors, it mostly adds another layer of ridiculous cuteness to already enormous feet. Even the paws have accessories."),
("Why cats sit on your keyboard","Your keyboard is warm, elevated, and directly between you and whatever has your attention. From a cat's perspective, that makes it premium real estate. A Maine Coon adds the bonus feature of covering nearly the entire workspace. Productivity has left the chat."),
("Why Maine Coons are so vocal","Maine Coons can use a surprisingly wide range of chirps, trills, meows, and little conversational noises. Vocal behavior varies by cat, but many owners describe them as unusually talkative companions. The funniest part is hearing delicate sounds come from such a massive animal. House of Big Beans has entered the group chat."),
("Why cats rub against furniture","Cats rub their cheeks and bodies against objects partly to leave familiar scent from specialized glands. That helps make their environment smell safe and recognizable. Furniture, door frames, and humans can all become part of the scent map. You thought you owned the couch; the paperwork says otherwise."),
("The Maine Coon chest ruff","That dramatic mane around a Maine Coon's chest is called a ruff. It becomes especially thick in colder seasons and contributes to the breed's famous lion-like look. The ruff can make an ordinary sit look like a royal portrait. Every room is a throne room if the cat is fluffy enough."),
("Why cats watch you cook","Cooking combines movement, interesting smells, noises, and the possibility that food might appear. A curious cat has several good reasons to monitor the process from a safe distance. A Maine Coon may treat the kitchen like a live cooking show. The critic has arrived before dinner is finished."),
("Why Maine Coons need big cat trees","A sturdy cat tree gives a large cat room to climb, stretch, scratch, and rest above the floor. Maine Coons need platforms and posts that can actually support their size. A tiny cat tower may technically be furniture, but physics gets the final vote. Big Beans require big infrastructure."),
("Why cats love sunbeams","Cats often seek sunny spots because warmth lets them relax without using as much energy to maintain body temperature. A patch of sunlight can turn the floor into the best seat in the house. Add a giant fluffy Maine Coon and suddenly the sunbeam is fully booked. Reservations are not accepted."),
("Why Maine Coons look bigger when they fluff up","Long guard hairs, a thick undercoat, and an enormous tail can make a Maine Coon appear even larger than its actual body. Cold weather and excitement can increase the fluffy effect. The result is a cat that seems capable of doubling in volume. No inflation warning is provided."),
("Why cats sit in doorways","Doorways give cats a strategic place to observe multiple rooms while staying close to household activity. It is an efficient checkpoint for a curious animal. A Maine Coon can turn that checkpoint into a complete roadblock. Please present snacks for passage."),
("Maine Coon kittens grow into huge cats","A Maine Coon kitten may look small at first, but the breed can develop into an impressively large adult over several years. Big paws and long legs can hint at what is coming. The transformation from tiny fluff ball to hallway obstacle is gradual. One day you simply realize the cat has become furniture-sized.")
]

def choose_topic(for_date: dt.date):
    index=for_date.toordinal()%len(TOPICS)
    title,narration=TOPICS[index]
    return index,title,narration

def scene_prompts(topic,narration):
    sentences=[s.strip() for s in narration.replace("?","." ).split(".") if s.strip()]
    while len(sentences)<4: sentences.append(topic)
    anchors=["establishing portrait, curious expression, cozy home interior","playful action moment, dynamic pose, warm window light","close-up portrait, expressive amber eyes, detailed fur","funny satisfying ending pose, cozy room, cinematic golden light"]
    return ["Photorealistic vertical 9:16 social-media image of the SAME silver Maine Coon cat in every scene: very large fluffy silver tabby Maine Coon, tufted ears, amber-gold eyes, enormous plume tail, realistic anatomy, cozy modern home, no people. "+anchors[i]+f". Video topic: {topic}. Scene idea: {sentences[min(i,len(sentences)-1)]}. No text, captions, logos, watermark, extra limbs, duplicate cat, or distorted paws." for i in range(4)]

def generate_image(prompt,destination,*,api_key,model,seed):
    headers={"Content-Type":"application/json"}
    if api_key:
        headers["Authorization"]=f"Bearer {api_key}"
    response=requests.post(
        OPENMIND_IMAGE_URL,
        headers=headers,
        json={"model":model,"prompt":prompt,"size":"720x1280","response_format":"url","seed":seed},
        timeout=240,
    )
    response.raise_for_status()
    body=response.json()
    data=body.get("data") if isinstance(body,dict) else None
    if not isinstance(data,list) or not data:
        raise RuntimeError("Free AI image service returned no image.")
    item=data[0] if isinstance(data[0],dict) else {}
    if item.get("b64_json"):
        destination.write_bytes(base64.b64decode(item["b64_json"]))
    elif item.get("url"):
        image_response=requests.get(item["url"],timeout=240)
        image_response.raise_for_status()
        destination.write_bytes(image_response.content)
    else:
        raise RuntimeError("Free AI image service returned no downloadable image.")
    with Image.open(destination) as image:
        image.verify()

def create_smoke_images(directory,seed):
    paths=[]
    for i in range(4):
        p=directory/f"scene-{i+1}.jpg"
        img=Image.new("RGB",(720,1280),(80+i*25,95+i*18,110+i*12))
        d=ImageDraw.Draw(img); d.rectangle((130,260,590,1020),outline=(240,240,240),width=8); d.text((170,580),f"HouseOfBigBeans smoke scene {i+1}",fill=(255,255,255))
        img.save(p,quality=92); paths.append(p)
    return paths

def make_voice(narration,output):
    binary=shutil.which("espeak-ng") or shutil.which("espeak")
    if not binary: raise RuntimeError("espeak-ng or espeak is required.")
    subprocess.run([binary,"-v","en-us","-s","150","-p","45","-a","180","-w",str(output),narration],check=True,timeout=120)

def probe_duration(path):
    r=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)],check=True,capture_output=True,text=True,timeout=30)
    return float(r.stdout.strip())

def ass_time(seconds):
    cs=max(0,int(round(seconds*100))); h,rem=divmod(cs,360000); m,rem=divmod(rem,6000); s,c=divmod(rem,100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"

def write_captions(narration,duration,path):
    chunks=[x.strip()+"." for x in narration.split(".") if x.strip()]
    header="""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Short,DejaVu Sans,66,&H00FFFFFF,&H000000FF,&H00000000,&H70000000,-1,0,0,0,100,100,0,0,1,5,2,2,80,80,360,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines=[header.rstrip()]
    for i,chunk in enumerate(chunks):
        start=duration*i/len(chunks); end=duration*(i+1)/len(chunks); words=chunk.split(); rows=[]; cur=[]
        for word in words:
            if cur and len(" ".join(cur+[word]))>34: rows.append(" ".join(cur)); cur=[word]
            else: cur.append(word)
        if cur: rows.append(" ".join(cur))
        text=r"\N".join(rows[:3]).replace("{",r"\{").replace("}",r"\}")
        lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Short,,0,0,0,,{text}")
    path.write_text("\n".join(lines)+"\n",encoding="utf-8")

def render_video(images,narration_wav,narration,output):
    duration=probe_duration(narration_wav); scene=max(0.5,duration/len(images)); concat=output.with_suffix(".concat.txt"); ass=output.with_suffix(".ass")
    concat.write_text("".join(f"file '{p.resolve()}'\nduration {scene:.6f}\n" for p in images)+f"file '{images[-1].resolve()}'\n",encoding="utf-8"); write_captions(narration,duration,ass)
    try:
        subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-f","concat","-safe","0","-i",str(concat),"-i",str(narration_wav),"-vf",f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,ass={ass}","-af","loudnorm=I=-16:TP=-1.5:LRA=11","-r","30","-c:v","libx264","-preset","medium","-crf","20","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-shortest","-movflags","+faststart",str(output)],check=True,timeout=600)
    finally:
        concat.unlink(missing_ok=True); ass.unlink(missing_ok=True)
    if not output.is_file() or output.stat().st_size<10000: raise RuntimeError("Rendered video is missing or unexpectedly small.")

def metadata(topic):
    title=f"{topic} 🐱 #Shorts"[:100]
    description=f"Daily Maine Coon facts and funny cat behavior from House of Big Beans.\n\nToday's topic: {topic}\n\n#MaineCoon #Cats #CatShorts #HouseOfBigBeans #Shorts"
    return title,description

def run(for_date,outdir,*,api_key,model,smoke=False):
    outdir.mkdir(parents=True,exist_ok=True); idx,topic,narration=choose_topic(for_date); seed=int(for_date.strftime("%Y%m%d"))*10; prompts=scene_prompts(topic,narration)
    if smoke: images=create_smoke_images(outdir,seed)
    else:
        images=[]
        for i,prompt in enumerate(prompts):
            p=outdir/f"scene-{i+1}.jpg"; generate_image(prompt,p,api_key=api_key,model=model,seed=seed+i); images.append(p)
    voice=outdir/"narration.wav"; make_voice(narration,voice); video=outdir/"HouseOfBigBeans-daily.mp4"; render_video(images,voice,narration,video); title,description=metadata(topic)
    manifest={"date":for_date.isoformat(),"topic_index":idx,"topic":topic,"narration":narration,"title":title,"description":description,"video":str(video),"image_model":model,"smoke":smoke}
    (outdir/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8"); return manifest

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("--date",default=dt.date.today().isoformat()); p.add_argument("--outdir",default="outputs/daily"); p.add_argument("--image-model",default=os.getenv("OPENMIND_IMAGE_MODEL","pollinations/flux")); p.add_argument("--smoke",action="store_true"); p.add_argument("--upload",action="store_true"); p.add_argument("--privacy",choices=["private","unlisted","public"],default=os.getenv("YOUTUBE_PRIVACY_STATUS","public")); args=p.parse_args(argv)
    date=dt.date.fromisoformat(args.date); manifest=run(date,Path(args.outdir),api_key=os.getenv("OPENMIND_API_KEY",""),model=args.image_model,smoke=args.smoke); print(json.dumps(manifest,indent=2))
    if args.upload:
        sys.path.insert(0,str(ROOT/"src")); from youtube_api import refresh_access_token,upload_video
        client=Path(os.getenv("YOUTUBE_CLIENT_FILE","youtube_oauth_client.json")); token=Path(os.getenv("YOUTUBE_TOKEN_FILE",".youtube_oauth_token.json")); access=refresh_access_token(client,token)
        url=upload_video(Path(manifest["video"]),title=manifest["title"],description=manifest["description"],access_token=access,privacy_status=args.privacy); print(f"[OK] Uploaded {args.privacy}: {url}")
    return 0

if __name__=="__main__": raise SystemExit(main())
