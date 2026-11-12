export function parseFeatureCommand(command) {
    const match = /^features ([01]) ([01]) ([01]) ([01])$/.exec(command);
    return match === null ? null : match.slice(1).map(value => value === '1');
}

export function applyFeatureSettings(values, {Features, rotation, grab, borderless, tasks}) {
    Features.curvature.value = values[0];
    rotation.setEnabled(values[2]);
    grab.setEnabled(values[2] && values[3]);
    if (borderless !== null) borderless.setEnabled(values[1]);
    for (const entry of tasks.values()) {
        if (!values[0] && entry.session.getValue() > 0) entry.session.set(0);
        // An open menu must not keep callbacks for a feature just switched off.
        for (const attachment of entry.attachments) attachment.ticket.close();
    }
}
