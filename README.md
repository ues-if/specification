# Universal Eyeglass Socket Specification

This repository is scoped to the normative UES specification set only.

The maintained source documents are:

- `spec/technical-spec.adoc`
- `spec/compliance-test.adoc`

All diagrams required to render the specification are stored in `spec/diagrams/`.

## Building the Specification

```bash
make html
make pdf
```

`make html` renders HTML for both specification documents into `build/spec/`.
`make pdf` renders PDFs for both documents into the same directory.
