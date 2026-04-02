import readline from "readline"

export const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
})

export const screen_clear = () => {
    console.clear();
}

export const main_menu_display = () => {
    console.log('\t[1] - Show Current Settings');
    console.log('\t[2] - Settings');
    // console.log('\t[3] - Show Current Balance of your wallet');
    // console.log('\t[4] - Transfer Sol to Wsol in the main wallet');
    console.log('\t[3] - Start Trading');
    console.log('\t[4] - Sell Token');
    // console.log('\t[5] - Unwrap Wsol to Sol in the main wallet');
    console.log('\t[5] - Exit');
}

export const settings_display = () => {
    console.log('\t[1] - Contract Address of the Token');
    console.log('\t[2] - Pool Id of the token');
    console.log('\t[3] - Pumpfun token or not')
    console.log('\t[4] - Buying Amount');
    console.log('\t[5] - Slippage');
    console.log('\t[6] - Back');
    console.log('\t[7] - Exit');
}