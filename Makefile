# Makefile for Standard Glasses AsciiDoc Documentation

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
ORG = docs/organization.adoc

# Output files
INDEX_HTML = $(BUILD_DIR)/index.html
SPEC_HTML = $(BUILD_DIR)/spec/technical-spec.html
BUSINESS_HTML = $(BUILD_DIR)/docs/idea-and-business.html
ORG_HTML = $(BUILD_DIR)/docs/organization.html

SPEC_PDF = $(BUILD_DIR)/spec/technical-spec.pdf
BUSINESS_PDF = $(BUILD_DIR)/docs/idea-and-business.pdf
ORG_PDF = $(BUILD_DIR)/docs/organization.pdf

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
	@echo "  make org        - Build organization document"

html: $(INDEX_HTML) $(SPEC_HTML) $(BUSINESS_HTML) $(ORG_HTML)
	@echo "✓ HTML documentation generated successfully"

pdf: $(SPEC_PDF) $(BUSINESS_PDF) $(ORG_PDF)
	@echo "✓ PDF documentation generated successfully"

# Individual HTML targets
index: $(INDEX_HTML)

spec: $(SPEC_HTML)

business: $(BUSINESS_HTML)

org: $(ORG_HTML)

# HTML generation rules
$(INDEX_HTML): $(INDEX) | $(BUILD_DIR)
	@echo "Building $@..."
	$(ADOC) -o $@ $(INDEX)

$(SPEC_HTML): $(SPEC) | $(BUILD_DIR)/spec
	@echo "Building $@..."
	$(ADOC) -o $@ $(SPEC)

$(BUSINESS_HTML): $(BUSINESS) | $(BUILD_DIR)/docs
	@echo "Building $@..."
	$(ADOC) -o $@ $(BUSINESS)

$(ORG_HTML): $(ORG) | $(BUILD_DIR)/docs
	@echo "Building $@..."
	$(ADOC) -o $@ $(ORG)

# PDF generation rules
$(SPEC_PDF): $(SPEC) | $(BUILD_DIR)/spec
	@echo "Building $@..."
	$(ADOC_PDF) -o $@ $(SPEC)

$(BUSINESS_PDF): $(BUSINESS) | $(BUILD_DIR)/docs
	@echo "Building $@..."
	$(ADOC_PDF) -o $@ $(BUSINESS)

$(ORG_PDF): $(ORG) | $(BUILD_DIR)/docs
	@echo "Building $@..."
	$(ADOC_PDF) -o $@ $(ORG)

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
