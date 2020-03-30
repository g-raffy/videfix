# utf-8
import subprocess
import re
from enum import Enum, auto
import argparse
from pathlib import Path

RED   = "\033[1;31m"  
BLUE  = "\033[1;34m"
CYAN  = "\033[1;36m"
GREEN = "\033[0;32m"
RESET = "\033[0;0m"
BOLD    = "\033[;1m"
REVERSE = "\033[;7m"

class LanguageId(Enum):
    UNKNOWN = auto()
    ENGLISH = auto()
    FRENCH = auto()
    JAPANESE = auto()
    KOREAN = auto()

class Language:

    def __init__(self, language_id=None, language_name=None, language_iso=None):
        if language_id is not None:
            assert language_name is None and language_iso is None
            self.language_id = language_id
        if language_name is not None:
            assert language_id is None and language_iso is None
            self.language_id = Language.language_name_to_id[language_name]
        if language_iso is not None:
            assert language_id is None and language_name is None
            self.language_id = Language.language_iso_to_id[language_iso]

    def __str__(self):
        return Language.language_id_to_iso[self.language_id]

    def __repr__(self):
        return Language.language_id_to_iso[self.language_id]
    
    @property
    def iso(self):
        return Language.language_id_to_iso[self.language_id]

    language_iso_to_id = {
        'und': LanguageId.UNKNOWN,
        'eng': LanguageId.ENGLISH,
        'fre': LanguageId.FRENCH,
        'jpn': LanguageId.JAPANESE,
        'kor': LanguageId.KOREAN,
        }
    language_name_to_id = {
        'Unknown': LanguageId.UNKNOWN,
        'English': LanguageId.ENGLISH,
        'French': LanguageId.FRENCH,
        'Japanese': LanguageId.JAPANESE,
        'Korean': LanguageId.KOREAN,
        }
    language_id_to_iso = {
        LanguageId.UNKNOWN: 'und',
        LanguageId.ENGLISH: 'eng',
        LanguageId.FRENCH: 'fre',
        LanguageId.JAPANESE: 'jpn',
        LanguageId.KOREAN: 'kor',
        }

    @classmethod
    def names(cls):
        return Language.language_name_to_id.keys()

    @classmethod
    def isos(cls):
        return Language.language_iso_to_id.keys()

def execute_command(command):
    """
    :param list(str) command:
    :rtype int,str,str: 
    """
    completed_process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    #print(completed_process.stdout)
    #print(type(completed_process.stdout))
    return completed_process

def to_language_iso(iso_or_pseudo_iso):
    language_iso = iso_or_pseudo_iso
    if iso_or_pseudo_iso == 'fra':
        language_iso = 'fre'
    return language_iso


def _parse_audio_streams(ffprobe_stderr):
    """ gets audio track information from the following lines of the stderr output of ffprobe
        
        Stream #0:0(eng): Video: h264 (Main) (avc1 / 0x31637661), yuv420p(tv, smpte170m/smpte170m/bt709), 662x330 [SAR 32:27 DAR 10592:4455], 700 kb/s, 23.98 fps, 120 tbr, 48k tbn, 47.95 tbc (default)

        note: these lines are not present for avi movies.

    :param str ffprobe_stderr: standard error stream of ffprobe command
    """
    audio_stream_defs = []
    for line in ffprobe_stderr.split(b'\n'):
        #
        try:
            line_as_str = str(line, encoding='utf-8')
        except UnicodeDecodeError as e:  # pylint: disable=unused-variable
            line_as_str = str(line, encoding='latin_1')
        # print('stderr : %s' % line_as_str)
        match = re.match(r'^\s*Stream #([0-9]+):([0-9]+)\(([a-z]+)\): Audio:\s', line_as_str)
        if match:
            audio_stream_def = {}
            audio_stream_def['majorid'] = match.groups()[0]
            audio_stream_def['minorid'] = match.groups()[1]
            audio_stream_def['language_iso'] = to_language_iso(match.groups()[2])
            audio_stream_defs.append(audio_stream_def)

    return audio_stream_defs

def get_movie_track_languages(movie_file_path):
    """
    :param Path movie_file_path:
    :rtype list(Language):
    """
    assert isinstance(movie_file_path, Path)
    languages = []
    completed_process = execute_command(['ffprobe', movie_file_path.expanduser(), '-show_entries', 'stream_tags=language'])
    assert completed_process.returncode == 0
    #print(completed_process.stdout)
    #print(type(completed_process.stdout))
    ffprobe_stderr = completed_process.stderr
    audio_stream_defs = _parse_audio_streams(ffprobe_stderr)
    # print(audio_stream_defs)

    for audio_stream_def in audio_stream_defs:
        languages.append(Language(language_iso=audio_stream_def['language_iso']))
    if len(audio_stream_defs) == 0:
        # avi movie files can't store audio track language information in the audiostreams themselves. Instead, these information is stored as riff tags in the header of the file.
        # search for audiotrack language information from header (in IAS<n> riff tags)
        # https://exiftool.org/TagNames/RIFF.html

        for line in ffprobe_stderr.split(b'\n'):
            # print('stderr' + line)
            # match = re.match('^\s*IAS1\s+:\s*[a-zA-Z]+\s+$', line)
            try:
                line_as_str = str(line, encoding='utf-8')
            except UnicodeDecodeError as e:  # pylint: disable=unused-variable
                line_as_str = str(line, encoding='latin_1')
            match = re.match(r'^\s*IAS1\s+:\s*([a-zA-Z]+)\s*$', line_as_str)
            if match:
                language_iso = match.groups()[0]
                if language_iso in Language.names():
                    languages.append(Language(language_name=language_iso))
                if language_iso in Language.isos():
                    languages.append(Language(language_iso=language_iso))
                # print(language)
            # print(match)


        # for line in completed_process.stdout.split(b'\n'):
        #     # print(b'stdout' + line)
        #     match = re.match(r'^\s*TAG\s*:\s*language=([a-zA-Z]+)\s*$', str(line, encoding='utf-8'))
        #     if match:
        #         language_iso = to_language_iso(match.groups()[0])
        #         languages.append(Language(language_iso=language_iso))
        #         # print(language)
    return languages


class MovieContainerType(Enum):
    AVI = auto()
    MP4 = auto()
    MKV = auto()


def get_movie_container_type(movie_file_path):
    suffix = movie_file_path.suffix
    if suffix in ['.avi']:
        return MovieContainerType.AVI
    if suffix in ['.mp4']:
        return MovieContainerType.MP4
    if suffix in ['.mkv']:
        return MovieContainerType.MKV
    assert False, 'unexpected suffix : %s' % suffix
    

def set_movie_track_language(movie_file_path, language):
    """
    :param Path movie_file_path:
    :param Language language:
    """
    assert isinstance(movie_file_path, Path)
    # ffmpeg -y -i /media/graffy/raffychap2a/Video/Movies/1950\ -\ Cendrillon\ \[fr\].avi -c:a copy -metadata:s:a:0 language=fre output.avi
    output_file_path = Path('~/toto%s' % movie_file_path.suffix).expanduser()
    if get_movie_container_type(movie_file_path) == MovieContainerType.AVI:
        print('avi')
        # find a way to set riff IAS1 to the language
        # https://superuser.com/questions/783895/ffmpeg-edit-avi-metadata-and-audio-track-naming
        #     Took quite a long time for me to figure this out. I'm posting it here, because even after 3 years this thread is one of the first hits in google search: AVI (more specific: RIFF) does support language names but in opposite to mkv, the metadata is not stored in the stream but in the header using tags IAS1-9 for up to 9 different audio streams.
        #  
        #     ffmpeg -i input.avi -map 0 -codec copy -metadata IAS1=eng -metadata IAS2=ger output.avi
        #
        #     VLC ist pretty tolerant. If you enter ISO code "ger", VLC translates it to "Deutsch", if you enter "MyLang" instead, VLC displays "MyLang". Other software like Kodi needs the the correct ISO code. It would read "MyL" only and then display the language as unknown.
        #
        #     However, please be aware that ffmpeg does not just add the language but also changes other metadata. For example, audio interleave and preload data are different in output.avi, no idea if this is good or might result in audio out of sync. Check with MediaInfo or similar.


        # https://exiftool.org/TagNames/RIFF.html
        completed_process = execute_command(['ffmpeg', '-y', '-i', str(movie_file_path.expanduser(), 'utf-8'), '-c:v', 'copy', '-c:a', 'copy', '-metadata', 'IAS1=%s' % language.iso, output_file_path])
        assert completed_process.returncode == 0, completed_process.stderr
    else:
        print('not avi')
        # ffmpeg -i input.mp4 -map 0 -codec copy -metadata:s:a:0 language=eng -metadata:s:a:1 language=rus output.mp4
        completed_process = execute_command(['ffmpeg', '-y', '-i', str(movie_file_path.expanduser(), 'utf-8'), '-c:v', 'copy', '-c:a', 'copy', '-metadata:s:a:0', 'language=%s' % language.iso, output_file_path])
        assert completed_process.returncode == 0, completed_process.stderr


def fix_movie_file(movie_file_path):
    languages = get_movie_track_languages(movie_file_path)
    print(languages)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='edit metadata inside movie files')
    subparsers = parser.add_subparsers()
    subparsers.required = True
    subparsers.dest = 'command'

    show_audio_language_subparser = subparsers.add_parser("show-audio-languages", help="shows the audio track languages of the given video files")
    show_audio_language_subparser.add_argument('movie_file_paths', nargs='+')

    set_audio_language_subparser = subparsers.add_parser("set-audio-language", help="sets the audio track language of the given video file")
    set_audio_language_subparser.add_argument('--language', required=True, choices=Language.language_iso_to_id.keys())
    set_audio_language_subparser.add_argument('--movie-file-path', required=True)

    namespace = parser.parse_args()
    # print(namespace)

    if namespace.command == 'show-audio-languages':
        for movie_file_path in namespace.movie_file_paths:
            # print(movie_file_path)
            languages = get_movie_track_languages(Path(movie_file_path))
            print(Path(movie_file_path), BLUE, languages, RESET)

    if namespace.command == 'set-audio-language':
        set_movie_track_language(Path(namespace.movie_file_path), Language(language_iso=namespace.language))


        # fix_movie_file('/home/graffy/private/moviefixer.git/1954 - Godzilla (Gojira).avi')
        # fix_movie_file('/home/graffy/private/moviefixer.git/1954 - Seven Samurai [Jap,EngSub].avi')
        # fix_movie_file('/home/graffy/2018 - I want to eat your pancreas [jp].mp4')
        # fix_movie_file('/home/graffy/output.avi')
