import argparse
import glob
import multiprocessing as mp
import os
import time
from typing import List, Tuple

import regex
from pyknp import KNP

WHITE_LIST = regex.compile(r'[\p{Hiragana}\p{Katakana}\p{Han}、「」]+')
HIRAGANA = regex.compile(r'[\p{Hiragana}、「」]+')
# characters that do not represent one mora each / specific symbols
SUTEGANA = r'[ぁぃぅぇぉゃゅょァィゥェォャュョ、「」]'
MORA_PATTERN = {5, 12, 17, 24, 31}


def count_mora(pronunciation: str
               ) -> int:
    if HIRAGANA.fullmatch(pronunciation):
        return len(pronunciation) - len(regex.findall(SUTEGANA, pronunciation))
    else:
        raise ValueError


def cumsum(partial_sequence: List[List],
           l: int
           ) -> List[int]:
    mora_counts = []
    count = 0
    for i in range(l):
        count += sum(analysis[1] for analysis in partial_sequence[i])
        mora_counts.append(count)
    # return the cumulative sum of mora
    return mora_counts


def extract_poem(phrases: List[List],
                 index: int,
                 count: List[int]
                 ) -> List[List]:
    inversed = count[::-1]
    n = len(count)
    attention = [0,
                 n - inversed.index(5),
                 n - inversed.index(12),
                 n - inversed.index(17),
                 n - inversed.index(24),
                 n - inversed.index(31)]
    return [phrases[index + attention[i]:index + attention[i + 1]] for i in range(len(attention) - 1)]


# poem[mora][phrase][morpheme][analysis]
def criteria(poem: List[List]
             ) -> bool:
    beginning_condition = poem[0][0][0][2] not in {'助詞', '判定詞'}
    middle_condition = poem[2][-1][-1][2] in {'助詞', '特殊'}
    middle_condition |= '基本形' in poem[2][-1][-1][4]
    end_condition = poem[4][-1][-1][2] in {'接尾辞', '判定詞'}
    end_condition |= poem[4][-1][-1][3] == '終助詞'
    end_condition |= any(conjugation in poem[4][-1][-1][4] for conjugation in {'基本形', 'タ形'})
    return beginning_condition & middle_condition & end_condition


def extract_poems(lines: List[str],
                  jobs: int
                  ) -> List[Tuple]:
    knp = KNP(jumanpp=True)
    chunk_size = len(lines) // jobs + 1
    arguments = [(lines[i:i + chunk_size], knp) for i in range(0, len(lines), chunk_size)]
    with mp.Pool(jobs) as p:
        checked_chunks = p.starmap(_extract_poems, arguments)

    poems = []
    for chunk in checked_chunks:
        poems.extend(chunk)
    return poems


def _extract_poems(chunk: List[str],
                   knp: KNP
                   ) -> List[Tuple]:
    poems = []
    for line in chunk:
        if WHITE_LIST.fullmatch(line):
            try:
                parsed = knp.parse(line)
                phrases = [[(mrph.midasi, count_mora(mrph.yomi), mrph.hinsi, mrph.bunrui, mrph.katuyou2)
                            for mrph in bnst.mrph_list()]
                           for bnst in parsed.bnst_list()]
            except ValueError:
                continue
            n = len(phrases)  # the number of phrases
            mora_counts = [cumsum(phrases[start:], n - start) for start in range(n)]
            for index, mora_count in enumerate(mora_counts):
                if len(MORA_PATTERN - set(mora_count)) == 0:
                    poem = extract_poem(phrases, index, mora_count)
                    if criteria(poem):
                        poems.append((poem, line))
    return poems


def main():
    start = time.time()
    parser = argparse.ArgumentParser(description='extract_5-7-5-7-7_pattern')
    parser.add_argument('INPUT', help='path to input')
    parser.add_argument('--jobs', type=int, default=1, help='p')
    parser.add_argument('OUTPUT', default='None', help='path to output')
    args = parser.parse_args()

    # path = os.path.join(args.INPUT, '**/*.gz')
    path = os.path.join(args.INPUT, '*')
    input_files = glob.glob(path)
    output_files = [os.path.join(args.OUTPUT, str(i)) for i in range(len(input_files))]
    jobs = args.jobs

    for i, file in enumerate(input_files):
        with open(file, "r") as inp:
            lines = [sentence for line in inp for sentence in line.strip().split('。') if sentence]

        print('start processing' + f' file-{str(i)}')
        poems = extract_poems(lines, jobs)

        elapsed_time = time.time() - start
        print(f'{elapsed_time}seconds spend')

        print('start writing' + f' file-{str(i)}')
        with open(output_files[i], "w") as out:
            for poem in poems:
                p = ''.join([mrph[0] for mora in poem[0] for phrase in mora for mrph in phrase])
                out.write(p + '\t' + poem[1] + '\n')
    print('done')


if __name__ == '__main__':
    main()
