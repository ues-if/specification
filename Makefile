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
    ADOC_PDF = $(DOCKER_RUN) asciidoctor-pdf
else
    ADOC = asciidoctor
    ADOC_PDF = asciidoctor-pdf
endif

BROWSER = xdg-open

# Build directory
BUILD_DIR = build

# Source files
INDEX = index.adoc
SPEC = spec/technical-spec.adoc
BUSINESS = docs/idea-and-business.adoc

# Output files
INDEX_HTML = $(BUILD_DIR)/index.html
SPEC_HTML = $(BUILD_DIR)/spec/technical-spec.html
BUSINESS_HTML = $(BUILD_DIR)/docs/idea-and-business.html

SPEC_PDF = $(BUILD_DIR)/spec/technical-spec.pdf
BUSINESS_PDF = $(BUILD_DIR)/docs/idea-and-business.pdf

# Targets
.PHONY: all html pdf clean view help

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
	@echo "  make business   - Build business model document"
	@echo "  make cad        - Export CAD (STEP/STL) for all sizes"

html: $(INDEX_HTML) $(SPEC_HTML) $(BUSINESS_HTML)
	@echo "✓ HTML documentation generated successfully"

pdf: $(SPEC_PDF) $(BUSINESS_PDF)
	@echo "✓ PDF documentation generated successfully"

# Individual HTML targets
index: $(INDEX_HTML)

spec: $(SPEC_HTML)

business: $(BUSINESS_HTML)

# HTML generation rules
$(INDEX_HTML): $(INDEX) | $(BUILD_DIR)
	@echo "Building $@ (v$(VERSION))..."
	$(ADOC) $(ADOC_ATTRS) -o $@ $(INDEX)

$(SPEC_HTML): $(SPEC) | $(BUILD_DIR)/spec
	@echo "Building $@ (v$(VERSION))..."
	$(ADOC) $(ADOC_ATTRS) -o $@ $(SPEC)

$(BUSINESS_HTML): $(BUSINESS) | $(BUILD_DIR)/docs
	@echo "Building $@ (v$(VERSION))..."
	$(ADOC) $(ADOC_ATTRS) -o $@ $(BUSINESS)
	@cp -r docs/diagrams $(BUILD_DIR)/docs/diagrams

# PDF generation rules
$(SPEC_PDF): $(SPEC) | $(BUILD_DIR)/spec
	@echo "Building $@ (v$(VERSION))..."
	$(ADOC_PDF) $(ADOC_ATTRS) -o $@ $(SPEC)

$(BUSINESS_PDF): $(BUSINESS) | $(BUILD_DIR)/docs
	@echo "Building $@ (v$(VERSION))..."
	$(ADOC_PDF) $(ADOC_ATTRS) -o $@ $(BUSINESS)

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

$(BUILD_DIR)/docs:
	@mkdir -p $(BUILD_DIR)/docs

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
