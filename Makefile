# Makefile for Standard Glasses AsciiDoc Documentation

# ---------------------------------------------------------------------------
# Version — auto-detected from git tag, overridable: make VERSION=1.2.3
# ---------------------------------------------------------------------------
VERSION ?= $(shell git describe --tags --exact-match 2>/dev/null | sed 's/^v//' || git describe --tags --always 2>/dev/null || echo "dev")
REVDATE ?= $(shell date +%Y-%m-%d)

# Attributes injected into every asciidoctor call so docs show version + date
ADOC_ATTRS = -a revnumber=$(VERSION) -a revdate=$(REVDATE)

# Variables
# Use Docker if asciidoctor is not installed locally
DOCKER_IMAGE = asciidoctor/docker-asciidoctor:latest
DOCKER_RUN = docker run --rm -v $(PWD):/documents $(DOCKER_IMAGE)

# Try local first, fall back to Docker
ADOC := $(shell command -v asciidoctor 2> /dev/null)
ifndef ADOC
    ADOC = $(DOCKER_RUN) asciidoctor
else
    ADOC = asciidoctor
endif

ADOC_PDF := $(shell command -v asciidoctor-pdf 2> /dev/null)
ifndef ADOC_PDF
    ADOC_PDF = $(DOCKER_RUN) asciidoctor-pdf
else
    ADOC_PDF = asciidoctor-pdf
endif

RSVG_CONVERT := $(shell rsvg-convert --version >/dev/null 2>&1 && echo rsvg-convert || echo '$(DOCKER_RUN) rsvg-convert')

BROWSER = xdg-open

# Build directory
BUILD_DIR = build

# Source files
INDEX = index.adoc
SPEC = spec/technical-spec.adoc
COMPLIANCE_TEST = spec/compliance-test.adoc
DOCS_ADOC = $(wildcard docs/*.adoc)

# SVG logos and their PNG equivalents
SVG_LOGOS = $(wildcard images/*.svg)
PNG_LOGOS = $(patsubst images/%.svg,$(BUILD_DIR)/images/%.png,$(SVG_LOGOS))

# Output files
INDEX_HTML = $(BUILD_DIR)/index.html
SPEC_HTML = $(BUILD_DIR)/spec/technical-spec.html
COMPLIANCE_TEST_HTML = $(BUILD_DIR)/spec/compliance-test.html
DOCS_HTML = $(patsubst docs/%.adoc,$(BUILD_DIR)/docs/%.html,$(DOCS_ADOC))

SPEC_PDF = $(BUILD_DIR)/spec/technical-spec.pdf
DOCS_PDF = $(patsubst docs/%.adoc,$(BUILD_DIR)/docs/%.pdf,$(DOCS_ADOC))

# Targets
.PHONY: all html pdf logos clean view help

all: html

help:
	@echo "Universal Eyeglass Standard Documentation Build System"
	@echo ""
	@echo "Available targets:"
	@echo "  make html       - Generate HTML documentation (default)"
	@echo "  make pdf        - Generate PDF documentation"
	@echo "  make all        - Generate all HTML files"
	@echo "  make view       - Open HTML documentation in browser"
	@echo "  make clean      - Remove generated files"
	@echo "  make help       - Show this help message"
	@echo ""
	@echo "Individual targets:"
	@echo "  make index      - Build main index.html"
	@echo "  make spec       - Build technical specification"
	@echo "  make docs       - Build all docs/ documents"	@echo "  make logos      - Convert SVG logos to PNG"	@echo "  make cad        - Export CAD (STEP/STL) for all sizes"

html: $(INDEX_HTML) $(SPEC_HTML) $(COMPLIANCE_TEST_HTML) $(DOCS_HTML) $(PNG_LOGOS)
	@echo "✓ HTML documentation generated successfully"

logos: $(PNG_LOGOS)
	@echo "✓ SVG logos converted to PNG"

# SVG → PNG conversion
$(BUILD_DIR)/images/%.png: images/%.svg | $(BUILD_DIR)/images
	@echo "Converting $< → $@..."
	$(RSVG_CONVERT) --zoom 4 $< -o $@

pdf: $(SPEC_PDF) $(DOCS_PDF)
	@echo "✓ PDF documentation generated successfully"

# Individual HTML targets
index: $(INDEX_HTML)

spec: $(SPEC_HTML)

docs: $(DOCS_HTML)

# HTML generation rules
$(INDEX_HTML): $(INDEX) | $(BUILD_DIR)/images
	@echo "Building $@ (v$(VERSION))..."
	$(ADOC) $(ADOC_ATTRS) -o $@ $(INDEX)
	@cp -r images/* $(BUILD_DIR)/images/

$(SPEC_HTML): $(SPEC) | $(BUILD_DIR)/spec $(BUILD_DIR)/spec/diagrams
	@echo "Building $@ (v$(VERSION))..."
	$(ADOC) $(ADOC_ATTRS) -o $@ $(SPEC)
	@cp -r spec/diagrams/. $(BUILD_DIR)/spec/diagrams/

$(COMPLIANCE_TEST_HTML): $(COMPLIANCE_TEST) | $(BUILD_DIR)/spec $(BUILD_DIR)/spec/diagrams
	@echo "Building $@ (v$(VERSION))..."
	$(ADOC) $(ADOC_ATTRS) -o $@ $(COMPLIANCE_TEST)
	@cp -r spec/diagrams/. $(BUILD_DIR)/spec/diagrams/

$(BUILD_DIR)/docs/%.html: docs/%.adoc | $(BUILD_DIR)/docs $(BUILD_DIR)/images
	@echo "Building $@ (v$(VERSION))..."
	$(ADOC) $(ADOC_ATTRS) -o $@ $<
	@cp -r images/* $(BUILD_DIR)/images/

# PDF generation rules
$(SPEC_PDF): $(SPEC) | $(BUILD_DIR)/spec
	@echo "Building $@ (v$(VERSION))..."
	$(ADOC_PDF) $(ADOC_ATTRS) -o $@ $(SPEC)

$(BUILD_DIR)/docs/%.pdf: docs/%.adoc | $(BUILD_DIR)/docs
	@echo "Building $@ (v$(VERSION))..."
	$(ADOC_PDF) $(ADOC_ATTRS) -o $@ $<

# CAD export
cad: | $(BUILD_DIR)/cad
	@echo "Exporting CAD (v$(VERSION))..."
	python src/ues/export.py $(BUILD_DIR)/cad
	@echo "✓ CAD exported to $(BUILD_DIR)/cad"

$(BUILD_DIR)/cad:
	@mkdir -p $(BUILD_DIR)/cad

# Create build directories
$(BUILD_DIR):
	@mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/spec:
	@mkdir -p $(BUILD_DIR)/spec

$(BUILD_DIR)/spec/diagrams:
	@mkdir -p $(BUILD_DIR)/spec/diagrams

$(BUILD_DIR)/docs:
	@mkdir -p $(BUILD_DIR)/docs

$(BUILD_DIR)/images:
	@mkdir -p $(BUILD_DIR)/images

# View in browser
view: html
	@echo "Opening documentation in browser..."
	$(BROWSER) $(INDEX_HTML) 2>/dev/null || \
	open $(INDEX_HTML) 2>/dev/null || \
	echo "Please open $(INDEX_HTML) in your browser"

# Clean generated files
clean:
	@echo "Cleaning generated files..."
	rm -rf $(BUILD_DIR)
	@echo "✓ Clean complete"

# Watch for changes (requires entr or similar)
watch:
	@echo "Watching for changes... (requires 'entr' installed)"
	@echo "Install with: apt-get install entr (Linux) or brew install entr (macOS)"
	find . -name "*.adoc" | entr make html
