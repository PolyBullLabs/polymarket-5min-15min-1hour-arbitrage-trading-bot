import { Logger } from 'pino';
import dotenv from 'dotenv';
import fs from 'fs';
import { PublicKey } from '@solana/web3.js';

// Define the type for the JSON file content
export interface Data {
    privateKey: string;
    pubkey: string;
    solBalance: number | null;
    tokenBuyTx: string | null,
    tokenSellTx: string | null,
}


export const randVal = (min: number, max: number, count: number, total: number, isEven: boolean): number[] => {

    const arr: number[] = Array(count).fill(total / count);
    if (isEven) return arr

    if (max * count < total)
        throw new Error("Invalid input: max * count must be greater than or equal to total.")
    if (min * count > total)
        throw new Error("Invalid input: min * count must be less than or equal to total.")
    const average = total / count
    // Randomize pairs of elements
    for (let i = 0; i < count; i += 2) {
        // Generate a random adjustment within the range
        const adjustment = Math.random() * Math.min(max - average, average - min)
        // Add adjustment to one element and subtract from the other
        arr[i] += adjustment
        arr[i + 1] -= adjustment
    }
    // if (count % 2) arr.pop()
    return arr;
}


export const saveDataToFile = (newData: Data[], filePath: string = "data.json") => {
    try {
        let existingData: Data[] = [];

        // Check if the file exists
        if (fs.existsSync(filePath)) {
            // If the file exists, read its content
            const fileContent = fs.readFileSync(filePath, 'utf-8');
            existingData = JSON.parse(fileContent);
        }

        // Add the new data to the existing array
        existingData.push(...newData);

        // Write the updated data back to the file
        fs.writeFileSync(filePath, JSON.stringify(existingData, null, 2));

    } catch (error) {
        try {
            if (fs.existsSync(filePath)) {
                fs.unlinkSync(filePath);
                console.log(`File ${filePath} deleted and create new file.`);
            }
            fs.writeFileSync(filePath, JSON.stringify(newData, null, 2));
            console.log("File is saved successfully.")
        } catch (error) {
            console.log('Error saving data to JSON file:', error);
        }
    }
};

export const sleep = async (ms: number) => {
    await new Promise((resolve) => setTimeout(resolve, ms))
}


export function deleteConsoleLines(numLines: number) {
    for (let i = 0; i < numLines; i++) {
        process.stdout.moveCursor(0, -1); // Move cursor up one line
        process.stdout.clearLine(-1);        // Clear the line
    }
}


// Function to read JSON file
export function readJson(filename: string = "data.json"): Data[] {
    if (!fs.existsSync(filename)) {
        // If the file does not exist, create an empty array
        fs.writeFileSync(filename, '[]', 'utf-8');
    }
    const data = fs.readFileSync(filename, 'utf-8');
    return JSON.parse(data) as Data[];
}

// Function to write JSON file
export function writeJson(data: Data[], filename: string = "data.json",): void {
    fs.writeFileSync(filename, JSON.stringify(data, null, 4), 'utf-8');
}

// Function to edit JSON file content
export function editJson(newData: Partial<Data>, filename: string = "data.json"): void {
    if (!newData.pubkey) {
        console.log("Pubkey is not prvided as an argument")
        return
    }
    const wallets = readJson(filename);
    const index = wallets.findIndex(wallet => wallet.pubkey === newData.pubkey);
    if (index !== -1) {
        wallets[index] = { ...wallets[index], ...newData };
        writeJson(wallets, filename);
    } else {
        console.error(`Pubkey ${newData.pubkey} does not exist.`);
    }
}

export interface Settings {
    mint: null | PublicKey
    poolId: null | PublicKey
    isPump: Boolean
    amount: number
    slippage: number
}

export const saveSettingsToFile = (newData: Settings, filePath: string = "settings.json") => {
    try {
        let existingData: Settings

        // Check if the file exists
        if (fs.existsSync(filePath)) {
            try {
                // If the file exists, read its content
                const fileContent = fs.readFileSync(filePath, 'utf-8');
                existingData = JSON.parse(fileContent);
            } catch (parseError) {
                // If there is an error parsing the file, delete the corrupted file
                console.error('Error parsing JSON file, deleting corrupted file:', parseError);
                fs.unlinkSync(filePath);
            }
        }

        // Write the updated data back to the file
        fs.writeFileSync(filePath, JSON.stringify(newData, null, 2));

    } catch (error) {
        console.log('Error saving data to JSON file:', error);
    }
};

export function readSettings(filename: string = "settings.json"): SettingsStr {
    try {
        if (!fs.existsSync(filename)) {
            // If the file does not exist, create an empty array
            return {
                mint: "1",
                poolId: "1",
                isPump: true,
                amount: "0.001",
                slippage: "1",
            }
        }
        const data = fs.readFileSync(filename, 'utf-8');
        const parsedData = JSON.parse(data)
        return parsedData
    } catch (error) {
        return {
            mint: "1",
            poolId: "1",
            isPump: true,
            amount: "0.001",
            slippage: "1",
        }
    }
}

export interface SettingsStr {
    mint: null | string
    poolId: null | string
    isPump: null | Boolean
    amount: null | string
    slippage: null | string
}