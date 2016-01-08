#!/usr/bin/env python

from subprocess import Popen, PIPE, CalledProcessError
import sys
from mutagen.flac import FLAC
from mutagen.id3 import (
    ID3, APIC, RVA2, TALB, TBPM, TCMP, TCOM, TCON, TCOP, TDOR, TDRC, TENC,
    TEXT, TIPL, TIT1, TIT2, TIT3, TLAN, TMCL, TMED, TMOO, TPE1, TPE2, TPE3,
    TPE4, TPOS, TPUB, TRCK, TSOA, TSOP, TSOT, TSRC, TSST, TXXX, UFID)
import os
import shutil
import tempfile
from contextlib import contextmanager


class UnknownTag(RuntimeError):
    pass


def newer(f1, f2):
    return (not os.path.exists(f2) or
            int(os.path.getmtime(f1)) > int(os.path.getmtime(f2)))


@contextmanager
def mk_tmp_dir():
    name = tempfile.mkdtemp()
    try:
        yield name
    finally:
        shutil.rmtree(name)


def transcode(flac_filename, mp3_filename, bitrate=320):
    decoder_cmd = ['flac', '--decode', '--stdout', '--silent', flac_filename]
    encoder_cmd = ['lame', '--preset', 'standard', '--silent', '-', mp3_filename]
    decoder = Popen(decoder_cmd, stdout=PIPE)
    encoder = Popen(encoder_cmd, stdin=decoder.stdout, stdout=PIPE)
    decoder.stdout.close()  # allow decoder to receive SIGPIPE if encoder exits
    encoder.communicate()
    decoder.wait()
    if encoder.returncode != 0:
        raise CalledProcessError(encoder.returncode, ' '.join(encoder_cmd))
    if decoder.returncode != 0:
        raise CalledProcessError(decoder.returncode, ' '.join(decoder_cmd))


class Tagger(object):
    tag_map = {
        "album":         TALB,
        "bpm":           TBPM,
        "compilation":   TCMP,
        "composer":      TCOM,
        "genre":         TCON,
        "copyright":     TCOP,
        "originaldate":  TDOR,
        "date":          TDRC,
        "encodeby":      TENC,
        "lyricist":      TEXT,
        "grouping":      TIT1,
        "title":         TIT2,
        "subtitle":      TIT3,
        "language":      TLAN,
        "media":         TMED,
        "mood":          TMOO,
        "artist":        TPE1,
        "albumartist":   TPE2,
        "conductor":     TPE3,
        "remixer":       TPE4,
        "label":         TPUB,
        "albumsort":     TSOA,
        "artistsort":    TSOP,
        "titlesort":     TSOT,
        "isrc":          TSRC,
        "discsubtitle":  TSST,
    }

    text_tag_map = {
        "acoustid_id":                 u'Acoustid Id',
        "albumartistsort":             u'ALBUMARTISTSORT',
        "asin":                        u'ASIN',
        "barcode":                     u'BARCODE',
        "catalognumber":               u'CATALOGNUMBER',
        "musicbrainz_albumartistid":   u"MusicBrainz Album Artist Id",
        "musicbrainz_albumid":         u"MusicBrainz Album Id",
        "musicbrainz_artistid":        u"MusicBrainz Artist Id",
        "musicbrainz_discid":          u"MusicBrainz Disc Id",
        "musicbrainz_releasegroupid":  u"MusicBrainz Release Group Id",
        "musicbrainz_trmid":           u"MusicBrainz TRM Id",
        "musicbrainz_workid":          u"MusicBrainz Work Id",
        "musicip_puid":                u"MusicIP PUID",
        "releasecountry":              u"MusicBrainz Album Release Country",
        "releasestatus":               u"MusicBrainz Album Status",
        "releasetype":                 u"MusicBrainz Album Type",
        "script":                      u'SCRIPT',
    }

    def tag(self, flac_filename, mp3_filename):
        flac = FLAC(flac_filename)
        id3 = ID3()
        for tag, value in flac.iteritems():
            if tag in self.tag_map:
                id3.add(self.tag_map[tag](encoding=3, text=value))
            elif tag in self.text_tag_map:
                id3.add(TXXX(encoding=3, desc=self.text_tag_map[tag], text=value))
            elif tag == 'tracknumber':
                value[0] += self._total(flac, ['tracktotal', 'totaltracks'])
                id3.add(TRCK(encoding=3, text=value))
            elif tag == 'discnumber':
                value[0] += self._total(flac, ['disctotal', 'totaldiscs'])
                id3.add(TPOS(encoding=3, text=value))
            elif tag == 'musicbrainz_trackid':
                id3.add(UFID(u'http://musicbrainz.org', flac['musicbrainz_trackid']))
            elif tag == 'producer':
                id3.add(TIPL(encoding=3, people=[u'producer', value]))
            elif tag == 'performer':
                id3.add(TMCL(encoding=3, people=self._performers(value)))
            elif tag not in [
                    'tracktotal', 'totaltracks', 'disctotal', 'totaldiscs',
                    'replaygain_album_gain', 'replaygain_album_peak',
                    'replaygain_track_gain', 'replaygain_track_peak']:
                raise UnknownTag("%s=%s" % (tag, value))

        self._replaygain(flac, id3, 'album')
        self._replaygain(flac, id3, 'track')

        for pic in flac.pictures:
            tag = APIC(
                encoding=3,
                mime=pic.mime,
                type=pic.type,
                desc=pic.desc,
                data=pic.data)
            id3.add(tag)

        id3.save(mp3_filename)

    def _total(self, flac, total_tags):
        for tag in total_tags:
            if tag in flac:
                return u'/' + flac[tag][0]
        return u''

    def _replaygain(self, flac, id3, gain_type):
        gain_tag = 'replaygain_%s_gain' % gain_type
        peak_tag = 'replaygain_%s_peak' % gain_type
        if gain_tag in flac and peak_tag in flac:
            gain = float(flac[gain_tag][0][:-3])
            peak = float(flac[peak_tag][0][:-3])
            id3.add(RVA2(unicode(gain_type), 1, gain, peak))

    def _performers(self, people):
        return [x.rstrip(u')').rsplit(u' (', 1) for x in people]


def is_flac(f):
    return f.endswith('.flac')


def copy_pictures(src_root, files, dst_folder):
    def is_cover_art(f):
        return (
            f.endswith('.jpg')
            or f.endswith('.jpeg')
            or f.endswith('.png')
            or f.endswith('.bmp'))

    pictures = [os.path.join(src_root, f) for f in files if is_cover_art(f)]

    for picture in pictures:
        print(
            "[copy     ] %s => %s" % (os.path.basename(picture), dst_folder))
        shutil.copy2(picture, dst_folder)


def transcode_dir(flac_dir, mp3_dir):
    with mk_tmp_dir() as tmp_dir:
        for flac_root, dirs, files in os.walk(flac_dir):
            sub_dir = os.path.relpath(flac_root, flac_dir)
            mp3_root = os.path.normpath(os.path.join(mp3_dir, sub_dir))
            tmp_root = os.path.normpath(os.path.join(tmp_dir, sub_dir))

            if not os.path.exists(mp3_root):
                os.mkdir(mp3_root)
            shutil.copystat(flac_root, mp3_root)
            if not os.path.exists(tmp_root):
                os.mkdir(tmp_root)

            copy_pictures(flac_root, files, mp3_root)

            tagger = Tagger()
            for flac_file_name in files:
                if not is_flac(flac_file_name):
                    continue

                mp3_file_name = os.path.splitext(flac_file_name)[0] + '.mp3'
                flac = os.path.join(flac_root, flac_file_name)
                tmp = os.path.join(tmp_root, mp3_file_name)
                mp3 = os.path.join(mp3_root, mp3_file_name)

                if newer(flac, mp3):
                    print("[transcode] %s" % (os.path.join(sub_dir, flac_file_name)))
                    transcode(flac, tmp)
                    print("[tag      ] %s" % (os.path.join(sub_dir, mp3_file_name)))
                    tagger.tag(flac, tmp)
                    shutil.move(tmp, mp3)
                    shutil.copystat(flac, mp3)
                else:
                    print("[skip     ] %s" % (os.path.join(sub_dir, flac_file_name)))


def main():
    if os.path.isdir(sys.argv[1]):
        transcode_dir(sys.argv[1], sys.argv[2])

if __name__ == '__main__':
    main()
