export class ServiceError extends Error {
    constructor(message, kind = 'failed') {
        super(message)
        this.kind = kind
    }
}
