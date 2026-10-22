"""Export curriculum only; never read MyWebsite settings, database or students.

python tools/export_mywebsite_library.py /path/to/MyWebsite --output library.json
Existing generated bundles are deliberately not overwritten without --output.
"""
import argparse
import importlib
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve()))
    from academy.quiz_format import parse_quiz
    from academy.school_data.titles_ru import TITLES
    from academy.school_data.slides_ai import SLIDES
    output = []
    for course, module_name in [('Starter', 'starter'), ('Python', 'python'), ('AI Creator', 'ai')]:
        def read(name, attribute):
            return getattr(importlib.import_module('academy.school_data.' + name), attribute)
        modules = read(module_name, 'MODULES')
        quizzes = read('quizzes_' + module_name, 'QUIZZES')
        russian = read('quizzes_' + module_name + '_ru', 'QUIZZES')
        study = read('study_' + module_name, 'STUDY')
        study_ru = read('study_' + module_name + '_ru', 'STUDY')
        for module in modules:
            for topic in module.topics:
                questions, errors = parse_quiz(quizzes[topic.key])
                translated, translated_errors = parse_quiz(russian[topic.key])
                if errors or translated_errors or len(questions) != len(translated):
                    raise ValueError(f'{topic.key}: invalid question bank or translation')
                bank = []
                for index, ((text, choices), (text_ru, choices_ru)) in enumerate(zip(questions, translated)):
                    if [valid for _, valid in choices] != [valid for _, valid in choices_ru]:
                        raise ValueError(f'{topic.key}: answer ordering differs between languages')
                    bank.append({'id': f'{topic.key}-{index+1}', 'q': text, 'q_ru': text_ru,
                                 'options': [label for label, _ in choices],
                                 'options_ru': [label for label, _ in choices_ru],
                                 'answer': next(i for i, (_, valid) in enumerate(choices) if valid)})
                output.append({'slug': 'mywebsite-' + topic.key.lower(), 'course': course,
                               'topic': module.title, 'title': topic.title, 'title_ru': TITLES.get(topic.key, ''),
                               'body': study.get(topic.key, topic.description), 'body_ru': study_ru.get(topic.key, ''),
                               'exercise': topic.homework, 'resources': topic.resources,
                               'slides': SLIDES.get(topic.key, ''), 'questions': bank})
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'topics': len(output), 'questions': sum(len(d['questions']) for d in output)}))


if __name__ == '__main__':
    main()
