/**
 * Utility to handle proto imports across different environments
 */
export const getProtoClient = (name: string) => {
    try {
        return require(`../../src/proto/${name}`);
    } catch (e) {
        return require(`../../proto/${name}`);
    }
};
