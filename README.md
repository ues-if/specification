# Universal Eyeglass Standard: Interchangeable Lens Specification

An open, royalty-free standard for interchangeable prescription eyeglass lenses.

## Project Overview

This repository contains a multi-document AsciiDoc specification for the **Universal Eyeglass Standard** initiative—a proposal to create industry-wide standardized, interchangeable prescription lenses with fixed sizes that work across compatible frames.

### Core Concept

- **4 Standard Sizes**: XS (kids), S (small adults), M (average adults), L (large adults)
- **Universal Compatibility**: One set of prescription lenses works with any compliant frame
- **Tool-Free Installation**: Snap-fit mounting system for at-home lens replacement
- **Reduced Waste & Cost**: Replace broken frames without replacing expensive prescription lenses
- **Open Standard**: Royalty-free specification for industry-wide adoption

## Documentation Structure

The project is organized into three main documents:

1. **[Technical Specification](spec/technical-spec.adoc)** (`spec/technical-spec.adoc`)
   - Physical dimensions for four standard lens sizes
   - Optical parameters and reference points
   - Mechanical interface (snap-fit mounting system)
   - Quality, safety, and compliance requirements
   - Testing procedures and certification

2. **[Idea & Business Model](docs/idea-and-business.adoc)** (`docs/idea-and-business.adoc`)
   - Problem statement and proposed solution
   - Market analysis and opportunity
   - Business models (open standard vs. proprietary)
   - Implementation roadmap
   - Financial considerations

3. **[Main Index](index.adoc)** (`index.adoc`)
   - Project overview and navigation

## Building the Documentation

### Prerequisites

Install AsciiDoctor:

```bash
# On Ubuntu/Debian
sudo apt-get install asciidoctor

# On macOS
brew install asciidoctor

# Or using Ruby gems
gem install asciidoctor
```

For PDF generation (optional):

```bash
gem install asciidoctor-pdf
```

### Generate HTML

```bash
# Generate all HTML documents
asciidoctor index.adoc
asciidoctor spec/technical-spec.adoc
asciidoctor docs/idea-and-business.adoc

# Or use the provided Makefile
make html
```

### Generate PDF

```bash
# Generate PDF documents
asciidoctor-pdf spec/technical-spec.adoc
asciidoctor-pdf docs/idea-and-business.adoc

# Or use the Makefile
make pdf
```

### View Documentation

After building, open the HTML files in your browser:

```bash
# Open main index
firefox index.html  # or your preferred browser

# Or use the Makefile
make view
```

## Quick Start

```bash
# Clone the repository
git clone https://github.com/jorgecarleitao/universal-eyeglass-standard.git
cd universal-eyeglass-standard

# Build HTML documentation
make html

# View in browser
make view
```

## Project Status

**Version**: 0.1.0 (DRAFT)  
**Status**: Concept/Specification Development  
**Last Updated**: April 6, 2026

This specification is in early draft stage. The goal is to:

1. Refine the technical specification through expert review
2. Conduct freedom-to-operate patent analysis
3. Build prototype lenses and frames
4. Recruit founding industry partners
5. Form the Universal Eyeglass Standards Consortium
6. Launch pilot program

## Key Features of the Standard

- **Fixed Sizes**: 4 standardized aperture sizes (XS, S, M, L)
- **Rounded Square Shape**: Universal geometry that works with most frame styles
- **Snap-Fit Interface**: Tool-free installation with dual-depth peripheral groove
- **Optical Quality**: Supports full prescription range (-10D to +6D sphere, up to -4D cylinder)
- **Safety Compliant**: Meets ANSI Z87.1 and EN ISO 12312-1 standards
- **Patent-Conscious**: Designed around existing patents on interchangeable eyewear

## Patent and IP Considerations

The specification is designed with awareness of existing patents on modular eyewear systems (particularly WO2006043941 and related patents). Key differentiators:

- **Standardized sizes**: Industry-wide standard vs. proprietary implementations
- **Different mechanical interface**: Dual-depth peripheral groove vs. existing subframe systems
- **Open specification**: Creates prior art, royalty-free licensing

**Recommendation**: Conduct thorough freedom-to-operate analysis before commercial implementation.

## Contributing

This is intended as an **open standard**. Contributions, feedback, and implementation reports are welcome:

- Technical feedback on specification
- Optical engineering review
- Manufacturing feasibility input
- Business model suggestions
- Patent landscape insights

Please open an issue or submit a pull request.

## License

The specification documents are intended to be published under a royalty-free license that allows:

- Any party to implement the standard in products
- Creating derivative specifications (with attribution)
- Commercial and non-commercial use
- Distribution and reproduction

The Universal Eyeglass Standards Consortium will grant implementers a royalty-free, perpetual patent license for any specification-essential patents.

## Contact

**Project Repository**: https://github.com/jorgecarleitao/universal-eyeglass-standard  
**Future Organization**: Universal Eyeglass Standards Consortium (to be formed)

## Roadmap

- [ ] **Phase 1** (Months 1-6): Complete specification v1.0, develop prototypes, form consortium
- [ ] **Phase 2** (Months 7-18): Industry engagement, certification program, pilot production
- [ ] **Phase 3** (Months 19-36): Market launch, scaling production
- [ ] **Phase 4** (Years 3-5): Ecosystem maturity, specification v2.0

## Related Research

The idea builds on existing concepts:

- **Modular frames** (Dresden Vision): Parts interchangeable within one brand
- **Sports eyewear** (Wiley-X): Removable lens systems for tactical/sports use
- **RX inserts**: Prescription carriers for goggles and protective eyewear
- **Trial lenses**: Standardized optometry testing lenses (not for consumer use)

**Gap**: No universal consumer standard exists across brands.

## Acknowledgments

Based on research and concept development exploring the feasibility of standardized interchangeable prescription lenses.

---

*"One Set of Lenses, Unlimited Frames"*
