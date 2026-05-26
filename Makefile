# Makefile for UES specification documents

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

BROWSER = xdg-open

# Build directory
BUILD_DIR = build

# Source files
SPEC = spec/technical-spec.adoc
COMPLIANCE_TEST = spec/compliance-test.adoc

# Output files
SPEC_HTML = $(BUILD_DIR)/spec/technical-spec.html
COMPLIANCE_TEST_HTML = $(BUILD_DIR)/spec/compliance-test.html
SPEC_PDF = $(BUILD_DIR)/spec/technical-spec.pdf
COMPLIANCE_TEST_PDF = $(BUILD_DIR)/spec/compliance-test.pdf

# Targets
.PHONY: all html pdf clean view help spec compliance-test watch


all: html

help:
	@echo "Universal Eyeglass Socket specification build system"
	@echo ""
	@echo "Available targets:"
	@echo "  make html              - Generate HTML for the spec documents (default)"
	@echo "  make pdf               - Generate PDF for the spec documents"
	@echo "  make all               - Generate all HTML files"
	@echo "  make view              - Open the technical specification in a browser"
	@echo "  make clean      - Remove generated files"
	@echo "  make help       - Show this help message"
	@echo ""
	@echo "Individual targets:"
	@echo "  make spec              - Build the technical specification"
	@echo "  make compliance-test   - Build the compliance test procedures"

html: $(SPEC_HTML) $(COMPLIANCE_TEST_HTML)
	@echo "✓ HTML specification documents generated successfully"

pdf: $(SPEC_PDF) $(COMPLIANCE_TEST_PDF)
	@echo "✓ PDF specification documents generated successfully"

# Individual HTML targets
spec: $(SPEC_HTML)

compliance-test: $(COMPLIANCE_TEST_HTML)

# HTML generation rules
$(SPEC_HTML): $(SPEC) | $(BUILD_DIR)/spec $(BUILD_DIR)/spec/diagrams
	@echo "Building $@ (v$(VERSION))..."
	$(ADOC) $(ADOC_ATTRS) -o $@ $(SPEC)
	@cp -r spec/diagrams/. $(BUILD_DIR)/spec/diagrams/

$(COMPLIANCE_TEST_HTML): $(COMPLIANCE_TEST) | $(BUILD_DIR)/spec $(BUILD_DIR)/spec/diagrams
	@echo "Building $@ (v$(VERSION))..."
	$(ADOC) $(ADOC_ATTRS) -o $@ $(COMPLIANCE_TEST)
	@cp -r spec/diagrams/. $(BUILD_DIR)/spec/diagrams/

# PDF generation rules
$(SPEC_PDF): $(SPEC) | $(BUILD_DIR)/spec
	@echo "Building $@ (v$(VERSION))..."
	$(ADOC_PDF) $(ADOC_ATTRS) -o $@ $(SPEC)

$(COMPLIANCE_TEST_PDF): $(COMPLIANCE_TEST) | $(BUILD_DIR)/spec
	@echo "Building $@ (v$(VERSION))..."
	$(ADOC_PDF) $(ADOC_ATTRS) -o $@ $(COMPLIANCE_TEST)

# Create build directories
$(BUILD_DIR):
	@mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/spec:
	@mkdir -p $(BUILD_DIR)/spec

$(BUILD_DIR)/spec/diagrams:
	@mkdir -p $(BUILD_DIR)/spec/diagrams

# View in browser
view: html
	@echo "Opening technical specification in browser..."
	$(BROWSER) $(SPEC_HTML) 2>/dev/null || \
	open $(SPEC_HTML) 2>/dev/null || \
	echo "Please open $(SPEC_HTML) in your browser"

# Clean generated files
clean:
	@echo "Cleaning generated files..."
	rm -rf $(BUILD_DIR)
	@echo "✓ Clean complete"

# Watch for changes (requires entr or similar)
watch:
	@echo "Watching for changes... (requires 'entr' installed)"
	@echo "Install with: apt-get install entr (Linux) or brew install entr (macOS)"
	find spec -name "*.adoc" | entr make html
