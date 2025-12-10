# weakly_supervised_sea_ice

A repository containing files for a Quarto book that provides background and resources for the NSF Funded Collaborations in Artificial Intelligence and Geosciences (CAIG) project Weakly Supervised Learning to Address Label-Data Irregularities in S
ea-Ice Classification.  This is a three year collaboration between University of Colorado Denver Computer Science and the National Snow and Ice Data Center (NSIDC).

The introduction provides an overview of the project.  The Data section provides a description of the data used in the project.  The Methods section describes our approaches to the problem.

[NSF Award # 2531101](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2531101&HistoricalAwards=false)  
[NSF Award # 2531102](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2531102&HistoricalAwards=false)

## Contributing

We will follow a branching workflow.  To contribute to the book, first clone the repository.

```
git clone git@github.com:andypbarrett/weakly_supervised_sea_ice.git
```

Create a branch with a short but descriptive name.  Here, I am using
my initials and then a description of the modifications made in the
branch.

```
git branch apb-add-new-content
```

Switch into that branch.

```
git switch apb-add-new-content
```

Now you can start to add or modify content.

It is best to work on small changes and add and commit those changes.

```
git add data.qmd
git commit -m 'add description of sea ice drift data'
```

When you have finished making changes and are ready for others to review those changes, push the branch to the github repository.

```
git push -u origin apb-add-new-content
```

The first time you push a new branch, you will need to set the
upstream branch by adding `-u origin apb-add-new-content` to the `git
push` command.  For subsequent pushes, you only need to use `git push`

Then go to the GitHub repository.  You will see a message asking if
you want to create a pull request (PR) for the new branch.  Go ahead
and create a PR and tag some reviewers.

## Using Quarto

[Quarto](https://quarto.org/) is an open source scientific and
technical publishing system.  You create documents using plain text
markdown in a text editor.  You can also embed dynamic content and executable code in
Python, R and Julia, either in text documents or Jupyter Notebooks.

The structure of the book is defined in the `_quarto.yml` file.  You
can add chapters and chapter sections by adding paths to `.qmd` files
under the `chapters:` section of this YAML file.

To edit and add content to chapters or sections, edit the `qmd` file.

You can see changes to content as you make these changes by using `quarto preview`.  This renders the document in a web browser.

```
quarto preview
```

If you want to preview a single document you can use

```
quarto preview intro.qmd
```

The [Getting Started](https://quarto.org/docs/get-started/) section of the docs describes how to install `quarto` and start working with it.
