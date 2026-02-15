#!/usr/bin/env python3
"""Post-process pandoc LaTeX output into a proper academic manuscript."""

import re

# Read the pandoc body
with open('body_raw.tex', 'r') as f:
    body = f.read()

# --- Extract abstract and keywords ---
abstract_match = re.search(
    r'\\subsection\{Abstract\}.*?\n\n(.*?)\n\n\\textbf\{Keywords:\}(.*?)\n\n',
    body, re.DOTALL
)
abstract_text = abstract_match.group(1).strip() if abstract_match else ""
keywords_text = abstract_match.group(2).strip() if abstract_match else ""

# --- Remove everything before "1. Introduction" ---
intro_pos = body.find(r'\subsection{1. Introduction}')
if intro_pos > 0:
    body = body[intro_pos:]

# --- Remove horizontal rules ---
body = body.replace(r'\begin{center}\rule{0.5\linewidth}{0.5pt}\end{center}', '')

# --- Fix section hierarchy ---
body = re.sub(r'\\subsection\{(\d+)\.\s+(.*?)\}\\label\{.*?\}', r'\\section{\2}', body)
body = re.sub(r'\\subsubsection\{(\d+\.\d+)\s+(.*?)\}\\label\{.*?\}', r'\\subsection{\2}', body)
body = re.sub(r'\\paragraph\{(\d+\.\d+\.\d+)\s+(.*?)\}\\label\{.*?\}', r'\\subsubsection{\2}', body)
# Clean remaining labels
body = re.sub(r'(\\(?:sub)*section\{.*?\})\\label\{.*?\}', r'\1', body)

# --- Fix figure paths: ../figures/ -> figures/ ---
body = body.replace('../figures/', 'figures/')

# --- Fix pandocbounded images ---
body = re.sub(
    r'\\pandocbounded\{\\includegraphics\[keepaspectratio\]\{(.*?)\}\}',
    r'\\includegraphics[width=\\textwidth]{\1}',
    body
)

# --- Fix special characters ---
body = body.replace('η²', '$\\eta^2$')
body = body.replace('η', '$\\eta$')
body = body.replace('R²', '$R^2$')
body = body.replace('km²', 'km$^2$')
body = body.replace('ρ', '$\\rho$')
body = body.replace('σ', '$\\sigma$')
body = body.replace('μ', '$\\mu$')
body = body.replace('λ', '$\\lambda$')
body = body.replace(r'\textbar{}', '|')
body = body.replace(r'\textbar', '|')
body = body.replace(r'\textless{}', '<')
body = body.replace(r'\textless', '<')
body = body.replace(r'\textgreater{}', '>')
body = body.replace(r'\textgreater', '>')
body = body.replace('¹', '$^1$')
body = body.replace('²', '$^2$')

# --- Fix tightlist ---
body = body.replace(r'\tightlist', '')

# --- Fix back-matter sections ---
for sec in ['Acknowledgments', 'Declaration of Competing Interests',
            'Author Contributions',
            'Declaration of Generative AI and AI-assisted Technologies in the Writing Process',
            'Ethics Statement', 'Funding', 'Data Availability',
            'References', 'Supplementary Materials']:
    body = body.replace(f'\\subsection{{{sec}}}', f'\\section*{{{sec}}}')

# --- Build the complete document ---
preamble = r"""\documentclass[12pt,a4paper]{article}

% Encoding and fonts
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{microtype}

% Page layout
\usepackage[margin=2.5cm]{geometry}
\usepackage{setspace}
\onehalfspacing

% Math
\usepackage{amsmath,amssymb}

% Tables
\usepackage{longtable,booktabs,array}
\usepackage{calc}
\usepackage{etoolbox}
\makeatletter
\patchcmd\longtable{\par}{\if@noskipsec\mbox{}\fi\par}{}{}
\makeatother
\usepackage{footnote}
\makesavenoteenv{longtable}

% Graphics
\usepackage{graphicx}
\graphicspath{{../figures/}{figures/}{./}}
\def\fps@figure{htbp}

% Links
\usepackage[hidelinks]{hyperref}
\usepackage{url}
\urlstyle{same}

% Lists
\providecommand{\tightlist}{%
  \setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}

% Paragraph formatting
\setlength{\parindent}{0pt}
\setlength{\parskip}{6pt plus 2pt minus 1pt}
\setlength{\emergencystretch}{3em}

% Section numbering
\setcounter{secnumdepth}{3}

%% ============================================================
%% Title and Authors
%% ============================================================
\title{Spatiotemporal Traffic Congestion Patterns and Network Centrality in Indonesian Metropolitan Cities}

\author{%
  Firman Hadi\textsuperscript{1,*} \and
  Yasser Wahyuddin\textsuperscript{1} \and
  L.M. Sabri\textsuperscript{1} \and
  Agung Indrajit\textsuperscript{2}%
}

\date{}

\begin{document}

\maketitle

\noindent\textsuperscript{1} Department of Geodetic Engineering, Universitas Diponegoro, Semarang, Indonesia\\
\textsuperscript{2} Deputy for Green and Digital Transformation, Nusantara Capital Authority, Indonesia\\[6pt]
\textsuperscript{*} Corresponding Author: Firman Hadi (\href{mailto:firmanhadi21@lecturer.undip.ac.id}{firmanhadi21@lecturer.undip.ac.id})

\bigskip

%% ============================================================
%% Abstract
%% ============================================================
\begin{abstract}
"""

# Fix special chars in abstract too
abstract_clean = abstract_text
for old, new in [('η²', '$\\eta^2$'), ('R²', '$R^2$'),
                 (r'\textbar{}', '|'), (r'\textbar', '|'),
                 (r'\textless{}', '<'), (r'\textless', '<'),
                 (r'\textgreater{}', '>'), (r'\textgreater', '>')]:
    abstract_clean = abstract_clean.replace(old, new)

keywords_section = f"""\\end{{abstract}}

\\noindent\\textbf{{Keywords:}} {keywords_text}

\\newpage

%% ============================================================
%% Main Body
%% ============================================================
"""

footer = r"""
\end{document}
"""

with open('manuscript.tex', 'w') as f:
    f.write(preamble)
    f.write(abstract_clean)
    f.write('\n')
    f.write(keywords_section)
    f.write(body)
    f.write(footer)

print("Done! manuscript.tex created.")
