import { PublicKey } from "@solana/web3.js";
import { main_menu_display, rl, screen_clear, settings_display } from "./src/menu";
import { readSettings, saveSettingsToFile, sleep } from "./src/utils/utils";
import { swap, buy_monitor_autosell, mainKp } from "./src/layout/buy";
import { sell_token } from "./src/layout/sell";
import { PumpAmmSdk } from "@pump-fun/pump-swap-sdk";
import { solanaConnection } from "./src/constants";
import { BN } from "bn.js";

export const init = () => {
    screen_clear();
    console.log("Raydium Trading Bot");

    main_menu_display();

    rl.question("\t[Main] - Choice: ", async (answer: string) => {
        let choice = parseInt(answer);
        switch (choice) {
            case 1:
                show_settings();
                break;
            case 3:
                buy_monitor_autosell();
                break;
            case 4:
                sell_token();
                break;
            case 5:
                process.exit(1);
            default:
                console.log("\tInvalid choice!");
                await sleep(1500);
                init();
                break;
        }
    })
}

export const mainMenuWaiting = () => {
    rl.question('\x1b[32mpress Enter key to continue\x1b[0m', (answer: string) => {
        init()
    })
}

const show_settings = async () => {
    let data = readSettings()

    console.log("Current settings of Trading bot...")
    console.log(data)
    mainMenuWaiting()
}

init()
