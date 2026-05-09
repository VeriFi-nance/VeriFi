## Edge Cases

### Copy-Trading Dilution / Piggybacking
Bilgili bir yatırımcıyı kopyalayan bir grup, yatırımcının kazancını önemli ölçüde düşürür. 
Örnek, 50 tane tahmin yapılmış olsun. Sadece %30 evet demiş. Ünlü bir yatırımcı bu durumda evet tahmin etsin. İlk başta kazancı çok iyi: <Deger gir>. Sonra onun 30 takipçisi de arkasından evet'e bassın, yatırımcının kazancı ciddi şekilde düşer.

**Solution Idea:**
1. Eğer takip ettiğin birisiyle aynı tahminde bulunursan, ağırlığın %p düşer. 
2. Takip ettiğin insanların tahminlerini görmek için belli bir reputation score ödersin. 

İlk çözüm insanları tahmin yapmaktan caydırabilir, ikincisi ise başklarının tahminlerine bakmaktan.

### Late Adoption
Oylamaya geç katılan kullanıcılar, tahminleri doğru çıksa bile zarar edebilir.

Solution:
1. Don't share the total pool. Give correct voters their 10 point stake and distribute the stake of losers. In other words, change payout from
`payout_i = (10 * (n_yes_stakers + n_no _stakers)) × (weight_i / sum of weights on winning side)`
to
`payout_i = 10 + 10 * (n_no _stakers) × (weight_i / sum of weights on winning side)`

