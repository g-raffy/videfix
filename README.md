# videfix
a command line tool to ease video files metadata edition (title, audio track languages)


# features

- supports the video containers : avi, mp4 and mkv
- allows the user to display or set the audio language of audio tracks
- allows the user to interactively fix video files :
    - the audio track languages
    - the video title
- a flexible mechanism to suggest video title from the video file name

# requirements

- videfix requires python 3, the language in which it is written
- videfix uses ffmpeg toolset (https://ffmpeg.org/) as a backend, and more specifically the executables `ffmpeg` and `ffprobe`

# usage examples

to display the audio tracks languages of a set of video files:
``` sh
videfix.py show-audio-languages ~/videos/*.avi
```

```
/home/bob/videos/1976 - pinky pou.avi  [fra] 
/home/bob/videos/1976 - carroyage.avi  [und] 
/home/bob/videos/1997 - hypoman.avi  [jpn, eng] 
/home/bob/videos/2024 - the blue tortoise.avi  [und, und] 
```

to edit the title and audio track languages of a set of video files:
``` sh
videfix.py modify-metadata --fix-undefined-audio-languages --fix-title --add-title-guesser 'filename_re:^(?P<year>[0-9]+) - (?P<title>[^\\[.]+)' --movie-file-path ~/videos/*.avi
```

```
/home/bob/videos/1976 - pinky pou.avi :
Current track languages : [fra]
Choose a title (old title : '') : pinky pou
changing title from '' to 'pinky pou'

/home/bob/videos/1976 - carroyage.avi :
Current track languages : [und]
Choose a language for the undefined audiotrack #0 : fra
setting audio track languages to [fra]
Choose a title (old title : 'carroyage') : carroyage

/home/bob/videos/1997 - hypoman.avi:
Current track languages : [jpn, eng]
Choose a title (old title : '') : hypoman
changing title from '' to 'hypoman'

/home/bob/videos/2024 - the blue tortoise.avi  [und, und] :
Current track languages : [und, und]
Choose a language for the undefined audiotrack #0 : fre
 unexpected language fre : valid values are ['und', 'eng', 'fra', 'jpn', 'kor', 'spa'] 
Choose a language for the undefined audiotrack #0 : fra 
Choose a language for the undefined audiotrack #1 : eng
setting audio track languages to [fra, eng]
Choose a title (old title : '') : the blue tortoise
changing title from '' to 'the blue tortoise'
```




