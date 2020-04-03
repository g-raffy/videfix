#!/usr/bin/env python3
# # utf-8
import subprocess
import re
from enum import Enum, auto
import argparse
from pathlib import Path
import datetime
 

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
    SPANISH = auto()

class LanguageDef:

    def __init__(self, language_id, language_name, language_iso):
        """
        :param LanguageId language_id:
        :param str language_name:
        :param str language_iso: iso 639-2/T
        """
        self.language_id = language_id
        self.language_name = language_name
        self.language_iso = language_iso

class LanguageDefs:

    def __init__(self):
        self.language_defs = {}
        self.register_language_def(LanguageDef(LanguageId.UNKNOWN, 'Unknown', 'und'))
        self.register_language_def(LanguageDef(LanguageId.ENGLISH, 'English', 'eng'))
        self.register_language_def(LanguageDef(LanguageId.FRENCH, 'Francais', 'fra'))
        self.register_language_def(LanguageDef(LanguageId.JAPANESE, 'Japanese', 'jpn'))
        self.register_language_def(LanguageDef(LanguageId.KOREAN, 'Korean', 'kor'))
        self.register_language_def(LanguageDef(LanguageId.SPANISH, 'Espanol', 'spa'))
    
    def register_language_def(self, language_def):
        """
        :param LanguageDef language_def:
        """
        self.language_defs[language_def.language_id] = language_def

    def language_iso_to_id(self, language_iso):
        for language_def in self.language_defs.values():
            if language_def.language_iso == language_iso:
                return language_def.language_id

    def language_name_to_id(self, language_name):
        for language_def in self.language_defs.values():
            if language_def.language_name == language_name:
                return language_def.language_id

    def language_id_to_iso(self, language_id):
        return self.language_defs[language_id].language_iso

    def language_id_to_name(self, language_id):
        return self.language_defs[language_id].language_name

    def isos(self):
        return [language_def.language_iso for language_def in self.language_defs.values()]

    def names(self):
        return [language_def.language_name for language_def in self.language_defs.values()]

LANGUAGE_DEFS = LanguageDefs()

class Language:
    # we use iso 639-2/T codes https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes

    def __init__(self, language_id=None, language_name=None, language_iso=None):
        global LANGUAGE_DEFS
        if language_id is not None:
            assert language_name is None and language_iso is None
            self.language_id = language_id
        if language_name is not None:
            assert language_id is None and language_iso is None
            self.language_id = LANGUAGE_DEFS.language_name_to_id(language_name)
        if language_iso is not None:
            assert language_id is None and language_name is None
            self.language_id = LANGUAGE_DEFS.language_iso_to_id(language_iso)

    def __str__(self):
        global LANGUAGE_DEFS
        return LANGUAGE_DEFS.language_id_to_iso(self.language_id)

    def __repr__(self):
        global LANGUAGE_DEFS
        return LANGUAGE_DEFS.language_id_to_iso(self.language_id)
    
    @property
    def iso(self):
        global LANGUAGE_DEFS
        return LANGUAGE_DEFS.language_id_to_iso(self.language_id)

    @property
    def name(self):
        global LANGUAGE_DEFS
        return LANGUAGE_DEFS.language_id_to_name(self.language_id)

    @classmethod
    def names(cls):
        global LANGUAGE_DEFS
        return LANGUAGE_DEFS.names()

    @classmethod
    def isos(cls):
        global LANGUAGE_DEFS
        return LANGUAGE_DEFS.isos()


def execute_command(command):
    """
    :param list(str) command:
    :rtype int,str,str: 
    """
    completed_process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    #print(completed_process.stdout)
    #print(type(completed_process.stdout))
    return completed_process

def check_language_iso(iso_or_pseudo_iso):
    language_iso = iso_or_pseudo_iso
    norm = 'iso 639-2/T'
    if iso_or_pseudo_iso == 'fre':
        language_iso = 'fra'
        norm = 'iso 639-2/B'
    assert language_iso in Language.isos(), 'unexpected language iso : %s' % language_iso
    # https://medium.com/av-transcode/how-to-add-multiple-audio-tracks-to-a-single-video-using-ffmpeg-open-source-tool-27bff8cca30 :
    #   FFmpeg expects the language can be specified as an ISO 639–2/T or ISO 639–2/B (3 letters) code. ISO 639 is a set of international standards that lists shortcodes for language names.
    allowed_norms = ['iso 639-2/T', 'iso 639-2/B']  # not sure which norms are actually allowed
    if norm not in allowed_norms:
        print(RED, 'warning : %s is not in the norm %s, which is not the allowed norms %s language code; replaced with %s' % (iso_or_pseudo_iso, norm, allowed_norms, language_iso), RESET)
    return language_iso

def check_language_name(name_or_pseudo_name):
    language_name = name_or_pseudo_name
    #if language_name == 'Francais':
    #    language_name = 'French'
    assert language_name in Language.names(), 'unexpected language name : %s' % language_name
    if name_or_pseudo_name != language_name:
        print(RED, 'warning : %s is not an expected language name; replaced with %s' % (name_or_pseudo_name, language_name), RESET)
    return language_name


def _find_audio_tracks_defs(ffprobe_stderr):
    # avi movie files can't store audio track language information in the audiostreams themselves. Instead, these information is stored as riff tags in the header of the file.
    # search for audiotrack language information from header (in IAS<n> riff tags)
    # https://exiftool.org/TagNames/RIFF.html
    stream_language_defs = {}
    header_language_defs = {}

    for line in ffprobe_stderr.split(b'\n'):
        # print('stderr' + line)
        # match = re.match('^\s*IAS1\s+:\s*[a-zA-Z]+\s+$', line)
        try:
            line_as_str = str(line, encoding='utf-8')
        except UnicodeDecodeError as e:  # pylint: disable=unused-variable
            line_as_str = str(line, encoding='latin_1')
        #     IAS1            : English
        #     IAS1            : Japanese
        #     IAS1            : Francais
        match = re.match(r'^\s*IAS([0-9]+)\s+:\s*([a-zA-Z]+)\s*$', line_as_str)
        if match:
            audio_stream_def = {}
            track_index = int(match.groups()[0]) - 1
            assert track_index >= 0
            audio_stream_def['audio_track_id'] = track_index
            language_name = check_language_name(match.groups()[1])
            language_iso = Language(language_name=language_name).iso
            audio_stream_def['language_iso'] = language_iso
            audio_stream_def['from_header'] = 'IAS%s:%s' % (match.groups()[0], match.groups()[1])
            # if match.groups()[1] not in ['und']:
            #    print(match.groups()[1])
            header_language_defs[track_index] = audio_stream_def

        # for avi files :
        # Stream #0:1: Audio: mp3 (U[0][0][0] / 0x0055), 48000 Hz, stereo, s16p, 138 kb/s

        # for mp4 files :
        # Stream #0:0(und): Video: mpeg4 (mp4v / 0x7634706D), yuv420p, 576x432 [SAR 1:1 DAR 4:3], 1002 kb/s, 23.98 fps, 23.98 tbr, 24k tbn, 2 tbc (default)
        # Metadata:
        #   handler_name    : VideoHandler
        # Stream #0:1(jpn): Audio: mp3 (mp4a / 0x6134706D), 44100 Hz, mono, s16p, 96 kb/s (default)
        # Metadata:
        #   handler_name    : SoundHandler

        # print(line_as_str)
        match = re.match(r'^\s*Stream #([0-9]+):([0-9]+)([^\:]*): Audio:\s', line_as_str)
        if match:
            audio_stream_def = {}
            audio_stream_def['majorid'] = match.groups()[0]
            audio_stream_def['minorid'] = match.groups()[1]
            stream_id = '%s:%s' % (audio_stream_def['majorid'], audio_stream_def['minorid'])
            audio_stream_def['stream_id'] = stream_id

            language_substring = match.groups()[2]  # it is expected to look loke "(jpn)"
            if language_substring != '':
                # the language of the audio stream is defined
                match = re.match(r'^\(([a-z]+)\)$', language_substring)
                assert match, "unexpected case : '%s' is expected to be of the form '(<language-iso-639-code>)' " % language_substring
                
                audio_stream_def['language_iso'] = check_language_iso(match.groups()[0])
                audio_stream_def['from_stream'] = '%s' % match.groups()[0]
            else:
                audio_stream_def['language_iso'] = ''
                audio_stream_def['from_stream'] = ''
            stream_language_defs[stream_id] = audio_stream_def

    # print(header_language_defs)
    # print(stream_language_defs)
    assert len(header_language_defs) <= len(stream_language_defs), "the number of audio streams found in the header (%d) don't match the actual number of audio streams (%d)" % (len(header_language_defs), len(stream_language_defs))

    # sorted_track_ids = sorted([ audio_stream_def['stream_id'] for audio_stream_def in stream_language_defs.values() ])
    sorted_track_ids = sorted(stream_language_defs.keys())
    # print(sorted_track_ids)

    for audio_stream_def in header_language_defs.values():
        assert audio_stream_def['audio_track_id'] < len(stream_language_defs), "audio_stream_def %s 's references a non-existing stream index (%d)" % (str(audio_stream_def), audio_stream_def['audio_track_id'])


    for track_index in range(len(sorted_track_ids)):
        track_id = sorted_track_ids[track_index]
        audio_stream_def = stream_language_defs[track_id]
        if track_index in header_language_defs.keys():
            audio_stream_def['from_header'] = header_language_defs[track_index]['from_header']
            if audio_stream_def['language_iso'] == '':
                audio_stream_def['language_iso'] = header_language_defs[track_index]['language_iso']
            else:
                assert audio_stream_def['language_iso'] == header_language_defs[track_index]['language_iso']
        if audio_stream_def['language_iso'] == '':
            audio_stream_def['language_iso'] = 'und'

    return stream_language_defs

def get_movie_track_languages(movie_file_path):
    """
    :param Path movie_file_path:
    :rtype list(Language):
    """
    assert isinstance(movie_file_path, Path)
    # print(movie_file_path)
    languages = []
    completed_process = execute_command(['ffprobe', movie_file_path.expanduser(), '-show_entries', 'stream_tags=language'])
    assert completed_process.returncode == 0, completed_process.stderr
    ffprobe_stderr = completed_process.stderr
    header_language_defs = _find_audio_tracks_defs(ffprobe_stderr)
    for audio_stream_def in header_language_defs.values():
        # print(audio_stream_def)
        languages.append(Language(language_iso=audio_stream_def['language_iso']))

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
    

def create_backup(file_path):
    """
    :param Path file_path:
    """
    assert isinstance(file_path, Path)
    now_date = datetime.datetime.now()
    backup_file_path = file_path.with_name(file_path.stem + '.asof_' + now_date.strftime("%Y_%m_%d_%H_%M_%S")  + file_path.suffix)
    print(backup_file_path)
    completed_process = execute_command(['rsync', '-va', str(file_path.expanduser()), str(backup_file_path.expanduser())])
    assert completed_process.returncode == 0, completed_process.stderr

    return backup_file_path
    
class BackupMode(Enum):
    MODIFY_ORIGINAL=auto()
    MODIFY_BACKUP=auto()
    

def set_movie_track_languages(movie_file_path, languages):
    """
    :param Path movie_file_path:
    :param list(Language) language:
    """
    assert isinstance(movie_file_path, Path)

    audio_track_defs = get_movie_track_languages(movie_file_path)
    print("existing track defs: ", audio_track_defs)
    assert len(audio_track_defs) == len(languages), "unexpected number of languages in %s (%d languages are expected) " % (str(languages), len(audio_track_defs))

    backup_mode = BackupMode.MODIFY_BACKUP

    movie_backup_file_path = create_backup(movie_file_path)

    if backup_mode == BackupMode.MODIFY_BACKUP:
        src_movie_file_path = movie_file_path
        dst_movie_file_path = movie_backup_file_path
    elif backup_mode == BackupMode.MODIFY_ORIGINAL:
        src_movie_file_path = movie_backup_file_path
        dst_movie_file_path = movie_file_path
    else:
        assert False
    # sorted_track_ids = sorted(audio_track_defs.keys())
    command = []
    command.append('ffmpeg')
    command.append('-y')
    command.append('-i')
    command.append(src_movie_file_path.expanduser())
    command.append('-c:v')
    command.append('copy')
    command.append('-c:a')
    command.append('copy')
    for track_index in range(len(languages)):
        # track_id = sorted_track_ids[track_index]
        if get_movie_container_type(src_movie_file_path) == MovieContainerType.AVI:
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
            command.append('-metadata')
            command.append('IAS%d=%s' % (track_index + 1, languages[track_index].name))
        else:
            print('not avi')
            command.append('-metadata:s:a:%s' % track_index)
            command.append('language=%s' % languages[track_index].iso)

    command.append(dst_movie_file_path.expanduser())

    # ffmpeg -i input.mp4 -map 0 -codec copy -metadata:s:a:0 language=eng -metadata:s:a:1 language=rus output.mp4
    completed_process = execute_command(command)
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
    show_audio_language_subparser.add_argument('movie_file_path', nargs='+')

    set_audio_language_subparser = subparsers.add_parser("set-audio-language", help="sets the audio track language of the given video file")
    set_audio_language_subparser.add_argument('--languages', required=True, choices=LANGUAGE_DEFS.isos(), nargs='+')
    set_audio_language_subparser.add_argument('--movie-file-path', required=True)

    namespace = parser.parse_args()
    # print(namespace)

    if namespace.command == 'show-audio-languages':
        for movie_file_path in namespace.movie_file_path:
            # print(movie_file_path)
            try:
                languages = get_movie_track_languages(Path(movie_file_path))
                print(Path(movie_file_path), BLUE, languages, RESET)
            except:
                print(RED, "failed to process %s" % movie_file_path, RESET)
                raise

    if namespace.command == 'set-audio-language':
        set_movie_track_languages(Path(namespace.movie_file_path), [Language(language_iso=language_iso) for language_iso in namespace.languages ])

