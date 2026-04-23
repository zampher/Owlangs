/**
 * KaTeX math checker for backend.
 *
 * Usage: node katex_checker.js '<JSON_STRING>'
 * Input:  Array of {segment_index, math_blocks: [{content, display}]}
 * Output: Array of {segment_index, errors: [{content, display, error}]}
 */
const katex = require('./katex.js');

function main() {
    const raw = process.argv[2];
    if (!raw) {
        console.log(JSON.stringify([]));
        return;
    }

    let input;
    try {
        input = JSON.parse(raw);
    } catch (e) {
        console.error('Invalid JSON input:', e.message);
        process.exit(1);
    }

    const results = [];

    for (const seg of input) {
        const segErrors = [];
        const mathBlocks = seg.math_blocks || [];

        for (const block of mathBlocks) {
            try {
                katex.renderToString(block.content, {
                    displayMode: !!block.display,
                    throwOnError: true,
                });
            } catch (err) {
                segErrors.push({
                    content: block.content,
                    display: !!block.display,
                    error: err.message || String(err),
                });
            }
        }

        if (segErrors.length > 0) {
            results.push({
                segment_index: seg.segment_index,
                errors: segErrors,
            });
        }
    }

    console.log(JSON.stringify(results));
}

main();
