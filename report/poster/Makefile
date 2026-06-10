.PHONY: main clean FORCE

main: poster.pdf presentation.pdf baseline_poster.pdf

poster.pdf: FORCE
	latexmk -pdflatex='lualatex -interaction nonstopmode' -pdf poster.tex

presentation.pdf: FORCE
	latexmk -pdflatex='lualatex -interaction nonstopmode' -pdf presentation.tex

baseline_poster.pdf: FORCE
	latexmk -pdflatex='lualatex -interaction nonstopmode' -pdf baseline_poster.tex

clean:
	latexmk -pdf -C
